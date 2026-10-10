"""Turn model rows into cited facts. Anything that cannot be checked against its line is dropped."""
from __future__ import annotations

import re
from collections import Counter
from fractions import Fraction
from dataclasses import dataclass, field
from typing import Optional

from beneficia.extract.passes import RawRow
from beneficia.model import BoardRole, CaseFacts, ControlAgreement, Document, Field, Holding, LineRef
from beneficia.parties import PartyRegistry, fold, normalise
from beneficia.rules.fallback import normalise_role

NUM_RE = re.compile(r"\d[\d'’ .  ]*\d|\d")
NULLISH = {"null", "none", "", "n/a", "-", "unknown", "nicht angegeben", "inconnu"}
STOP = {"und", "et", "e", "der", "die", "das", "de", "du", "des", "la", "le", "di", "del", "von", "van",
        "ag", "sa", "gmbh", "sarl", "sagl", "srl", "spa", "ltd", "inc", "holding"}


@dataclass
class Resolution:
    facts: CaseFacts
    dropped: list[dict] = field(default_factory=list)
    accepted: Counter = field(default_factory=Counter)


def numbers_on(text: str) -> set[int]:
    out = set()
    for m in NUM_RE.finditer(text):
        raw = m.group(0)
        if re.search(r"\d\.\d{1,2}(\D|$)", raw) and "'" not in raw:  # decimals such as 12.5 or dates 12.03.
            for part in re.split(r"[.\s]", raw):
                if part.isdigit():
                    out.add(int(part))
        digits = re.sub(r"[^\d]", "", raw)
        if digits:
            out.add(int(digits))
        for part in re.split(r"[\s  ]+", raw):  # "9 6010" must still yield 9 and 6010
            d = re.sub(r"[^\d]", "", part)
            if d:
                out.add(int(d))
    return out


PERCENT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:%|prozent|pour ?cent|per ?cento)")


def percent_on(value: float, text: str) -> bool:
    """The percentage must be written on the line, e.g. '100 %', '25%', '33,5 %'."""
    for m in PERCENT_RE.finditer(fold(text)):
        if abs(float(m.group(1).replace(",", ".")) - float(value)) < 1e-9:
            return True
    return False


UNIT_WORDS = r"(parts?|actions?|aktien|stammanteile?|anteile?|quote|azioni|shares|quotas)"


def quantity_after(name: str, text: str) -> Optional[int]:
    """Number of units written right after a name, e.g. 'pour le compte de Thomas Berger, Genève : 80 parts'."""
    toks = _tokens(name)
    if not toks:
        return None
    hay = fold(text)
    pos = hay.rfind(toks[-1])
    if pos < 0:
        return None
    m = re.match(r"[^\d]{0,40}?(\d[\d'’ ]*)\s*" + UNIT_WORDS + r"\b", hay[pos + len(toks[-1]):])
    if not m:
        return None
    return int(re.sub(r"[^\d]", "", m.group(1)))


def _tokens(name: str) -> list[str]:
    return [w for w in normalise(name).split() if len(w) >= 3 and w not in STOP]


def name_on(name: str, text: str) -> bool:
    toks = _tokens(name)
    if not toks:
        return fold(name).strip() in fold(text)
    hay = normalise(text)
    return any(t in hay for t in toks)


class Resolver:
    def __init__(self, docs: dict[str, Document], target: Optional[str]):
        self.docs = docs
        self.reg = PartyRegistry()
        self.target_name = target
        self.dropped: list[dict] = []
        self.accepted: Counter = Counter()
        self.holdings: list[Holding] = []
        self.agreements: list[ControlAgreement] = []
        self.board: list[BoardRole] = []
        self.totals: dict[str, list[tuple[int, str, LineRef]]] = {}
        if target:
            self.reg.get_or_create(target, None, "legal_entity")

    def _ref(self, row: RawRow) -> LineRef:
        m = re.match(r"P(\d+)\.L(\d+)", row.line_id)
        return LineRef(row.doc, int(m.group(1)), int(m.group(2)))

    def _context(self, ref: LineRef, span: int = 1) -> str:
        doc = self.docs[ref.doc]
        parts = [doc.line(ref.page, ref.line + d) for d in range(-span, span + 1)]
        return " ".join(p for p in parts if p)

    def _drop(self, row: RawRow, why: str) -> None:
        self.dropped.append({"pass": row.pass_name, "ref": f"{row.doc}.{row.line_id}", "values": row.values,
                             "reason": why})

    def add(self, row: RawRow) -> None:
        row.values = [None if isinstance(v, str) and v.strip().lower() in NULLISH else v for v in row.values]
        ref = self._ref(row)
        if self.docs[ref.doc].line(ref.page, ref.line) is None:
            return self._drop(row, "line_not_found")
        ctx = self._context(ref)
        handler = getattr(self, "_" + row.pass_name.removesuffix("_prose"))
        if handler(row, ref, ctx) is not False:
            self.accepted[row.pass_name] += 1

    def _companies(self, row, ref, ctx):
        name, legal_form, seat, total, kind = row.values
        known = self.reg.find(name) or self._target_alias(name)
        if not name or not (name_on(name, self._context(ref, 3)) or known):
            return self._drop(row, "name_not_on_line")
        if known is not None:
            name = known.name
        if not _entity(name) and not legal_form:
            return self._drop(row, "not_a_legal_entity")
        party = self.reg.get_or_create(name, ref, "legal_entity")
        if legal_form:
            party.fields.setdefault("legal_form", Field(legal_form, ref))
        if seat:
            party.fields.setdefault("seat", Field(seat, ref))
        if total is not None:
            if total <= 0 or total not in numbers_on(ctx):
                self._drop(row, "total_not_on_line")
            else:
                self.totals.setdefault(party.id, []).append((total, kind or "shares", ref))

    def _holdings(self, row, ref, ctx):
        holder, company, units, percent, held_for, basis = row.values
        if not holder or not company:
            return self._drop(row, "missing_party")
        if units is not None and percent_on(units, ctx) and units not in numbers_on(PERCENT_RE.sub(" ", fold(ctx))):
            units, percent = None, units  # the number is only written as a percentage on the line
        if units is not None and (units <= 0 or units not in numbers_on(ctx)):
            return self._drop(row, "units_not_on_line")
        written = None
        if units is None:
            if percent is None or not (0 < percent <= 100) or not percent_on(percent, ctx):
                after = quantity_after(held_for, ctx) if held_for else None
                if after is not None and name_on(holder, ctx):
                    units = after  # quantity written right after the principal's name (wrapped line)
                elif held_for and name_on(held_for, ctx) and name_on(holder, ctx):
                    # fiduciary holding without a readable quantity: keep it as a fiduciary item for review
                    nominee = self.reg.get_or_create(holder, ref)
                    principal = self.reg.get_or_create(held_for, ref)
                    comp = self.reg.find(company) or self._target_alias(company)
                    self.agreements.append(ControlAgreement("fiduciary", principal.id, nominee.id,
                                                            comp.id if comp else None, ref))
                    return None
                else:
                    return self._drop(row, "units_missing")
            else:
                written = Fraction(str(percent)) / 100
        if not name_on(holder, ctx):
            return self._drop(row, "holder_not_on_line")
        comp = self.reg.find(company) or self._target_alias(company)
        if comp is None:
            if not name_on(company, self._context(ref, 40)):
                return self._drop(row, "company_not_in_document")
            comp = self.reg.get_or_create(company, ref, "legal_entity")
        h = self.reg.get_or_create(holder, ref)
        principal = None
        if held_for:
            if not name_on(held_for, ctx):
                return self._drop(row, "principal_not_on_line")
            principal = self.reg.get_or_create(held_for, ref, "natural_person"
                                               if not _entity(held_for) else "legal_entity").id
        if h.id == comp.id:
            return self._drop(row, "self_holding")
        self.holdings.append(Holding(h.id, comp.id, int(units) if units is not None else 0, basis or "both",
                                     principal, written, ref))

    def _target_alias(self, name: str):
        if self.target_name and normalise(name) and normalise(name) in normalise(self.target_name):
            return self.reg.find(self.target_name)
        return None

    def _agreements(self, row, ref, ctx):
        kind, controller, controlled, company = row.values
        wide = self._context(ref, 2)
        if not controller or not name_on(controller, wide):
            return self._drop(row, "controller_not_on_line")
        if not controlled or not name_on(controlled, wide):
            return self._drop(row, "controlled_not_on_line")
        c1 = self.reg.get_or_create(controller, ref)
        c2 = self.reg.get_or_create(controlled, ref)
        comp = self.reg.find(company) if company else None
        self.agreements.append(ControlAgreement(kind, c1.id, c2.id, comp.id if comp else None, ref))

    def _board(self, row, ref, ctx):
        person, company, role_raw = row.values
        if not person or not name_on(person, ctx):
            return self._drop(row, "person_not_on_line")
        p = self.reg.get_or_create(person, ref, "natural_person")
        comp = (self.reg.find(company) or self._target_alias(company)) if company else None
        self.board.append(BoardRole(p.id, comp.id if comp else None, role_raw or "", normalise_role(role_raw or ""),
                                    ref))

    def _persons(self, row, ref, ctx):
        name, birth, nationality, residence = row.values
        if not name or not name_on(name, ctx) or _entity(name):
            return self._drop(row, "name_not_on_line")
        p = self.reg.get_or_create(name, ref, "natural_person")
        for key, val in (("birth_date", birth), ("nationality", nationality), ("residence", residence)):
            if val and key not in p.fields:
                if name_on(val, ctx) or any(n in numbers_on(ctx) for n in numbers_on(val)):
                    p.fields[key] = Field(val, ref)

    def finish(self) -> Resolution:
        target = None
        if self.target_name:
            target = self.reg.get_or_create(self.target_name, None, "legal_entity")
        else:  # the company with the most holdings in it
            counts = Counter(h.company for h in self.holdings)
            if counts:
                target = self.reg.parties[counts.most_common(1)[0][0]]
        for pid, items in self.totals.items():
            party = self.reg.parties[pid]
            cap = [(t, r) for t, k, r in items if k != "votes"]
            votes = [(t, r) for t, k, r in items if k == "votes"]
            if cap:
                party.total_capital, party.total_ref = cap[0]
            if votes:
                party.total_votes = votes[0][0]
        # the same holding cited twice (register and agreement, or window overlap) is counted once
        seen, unique = set(), []
        for h in self.holdings:
            key = (h.holder, h.company, h.units_held, h.written_percent, h.basis, h.held_for)
            if key in seen:
                continue
            seen.add(key)
            unique.append(h)
        # a voting agreement binds a shareholder; anything else is not a voting agreement we can use
        agreements = []
        for ag in self.agreements:
            comp = ag.company or (target.id if target else None)
            if ag.kind == "voting":
                bound = {h.holder for h in unique if h.company == comp} | {h.held_for for h in unique
                                                                           if h.company == comp and h.held_for}
                if ag.controlled == comp or ag.controller == ag.controlled or ag.controlled not in bound:
                    self.dropped.append({"pass": "agreements", "ref": str(ag.ref), "reason":
                                         "controlled_party_not_shareholder",
                                         "values": [ag.kind, ag.controller, ag.controlled, ag.company]})
                    continue
            agreements.append(ag)
        facts = CaseFacts(target.id if target else "", self.reg.parties, unique, agreements, self.board)
        res = Resolution(facts, self.dropped, self.accepted)
        res.totals_seen = self.totals  # conflicting totals are checked by validate
        return res


def _entity(name: str) -> bool:
    from beneficia.parties import looks_like_entity
    return looks_like_entity(name)
