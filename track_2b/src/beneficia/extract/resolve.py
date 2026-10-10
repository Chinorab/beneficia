"""Turn model rows into cited facts. Anything that cannot be checked against its line is dropped."""
from __future__ import annotations

import re
from collections import Counter
from fractions import Fraction
from dataclasses import dataclass, field
from typing import Optional

from beneficia.extract.passes import CAPITAL_LINE, RawRow

# words that show an agreement or control clause is really written near the cited line (accents folded)
AGREEMENT_EVIDENCE = re.compile(
    r"(stimmbind|bindungsvertrag|aktionarbindung|weisung|treuhand|fiduci|pacte|convention de vote|"
    r"convention d'actionnaires|instructions? de|patto|parasocial|istruzion|veto|ernenn|abberuf|nommer|"
    r"revoquer|nominare|revocare|stimmrecht.*aus|droit de vote.*selon|for the account|on behalf|"
    r"pour le compte|per conto|im auftrag|auf rechnung)")
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


POSTAL = re.compile(r"\b(\d{4})\s+[A-ZÄÖÜÉÈ][a-zäöüéèàç]")
REGISTER_TITLE = re.compile(r"(aktienbuch|anteilbuch|gesellschafterliste|registre|libro (delle )?(azioni|quote)|"
                            r"register)", re.IGNORECASE)


def postal_codes(text: str) -> set[int]:
    return {int(m.group(1)) for m in POSTAL.finditer(text)}


def name_full_on(name: str, text: str) -> bool:
    toks = _tokens(name)
    hay = normalise(text)
    return bool(toks) and all(t in hay for t in toks)


def register_owner(doc, ref) -> Optional[str]:
    """The nearest line above the cited one, on the same page, that titles a register or states a capital."""
    for n in range(ref.line - 1, 0, -1):
        line = doc.line(ref.page, n)
        if line and (REGISTER_TITLE.search(line) or CAPITAL_LINE.search(line)) and _entity(line):
            return line
    return None


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
        handler = getattr(self, "_holdings" if row.pass_name.startswith("holdings") else "_" + row.pass_name)
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
            self._add_total(party, total, kind, ref, row)

    def _add_total(self, party, total, kind, ref, row) -> None:
        # the total must sit on a capital line: the cited one, or the line just after or before it
        # (models often cite the heading that names the company); the citation moves to that line
        doc = self.docs[ref.doc]
        hit = None
        for delta in (0, 1, -1):
            line = doc.line(ref.page, ref.line + delta) or ""
            if total > 0 and total in numbers_on(line) and CAPITAL_LINE.search(line):
                hit = LineRef(ref.doc, ref.page, ref.line + delta)
                break
        if hit is None:
            self._drop(row, "total_not_on_capital_line")  # e.g. a holding row read as the company's capital
        else:
            self.totals.setdefault(party.id, []).append((total, kind or "shares", hit))

    def _capital(self, row, ref, ctx):
        company, total, kind = row.values
        if total is None:
            return self._drop(row, "total_missing")
        line = self.docs[ref.doc].line(ref.page, ref.line) or ""
        party = None
        if company and (name_full_on(company, ctx) or name_full_on(company, register_owner(self.docs[ref.doc], ref) or "")):
            party = self.reg.find(company) or self._target_alias(company)
            if party is None and _entity(company):
                party = self.reg.get_or_create(company, ref, "legal_entity")
        if party is None:
            party = self._party_named_in(line) or self._party_named_in(register_owner(self.docs[ref.doc], ref) or "")
        if party is None:
            return self._drop(row, "company_not_resolved")
        self._add_total(party, total, kind, ref, row)

    def _holdings(self, row, ref, ctx):
        holder, company, units, percent, held_for, basis = row.values
        if not holder:
            return self._drop(row, "missing_party")
        # holder and quantity must be on the cited line itself (the prose pass merged a wrapped line with the
        # next one). A citation off by one line is re-anchored to the neighbour that carries both, never widened.
        doc = self.docs[ref.doc]

        def own_text(r: LineRef) -> str:
            nxt = doc.line(r.page, r.line + 1) if row.pass_name == "holdings_prose" else None
            return " ".join(x for x in (doc.line(r.page, r.line), nxt) if x)

        anchor = None
        for delta in (0, 1, -1):
            cand = LineRef(ref.doc, ref.page, ref.line + delta)
            text = own_text(cand)
            if text and name_on(holder, text) and (units is None or units in numbers_on(text)):
                anchor = cand
                break
        if anchor is None:
            return self._drop(row, "holder_or_units_not_on_line")
        if anchor != ref:
            self.accepted["citation_reanchored"] += 1
            ref, ctx = anchor, self._context(anchor)
        own = own_text(ref)
        if units is not None and percent_on(units, own) and units not in numbers_on(PERCENT_RE.sub(" ", fold(own))):
            units, percent = None, units  # the number is only written as a percentage on the line
        if units is not None and (units <= 0 or units not in numbers_on(own)):
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
        if not name_on(holder, own):
            return self._drop(row, "holder_not_on_line")
        if units is not None and units in postal_codes(own):
            return self._drop(row, "units_is_postal_code")  # '1700 Fribourg' is an address, not 1700 shares
        comp = self._resolve_company(company, holder, units, ref, own)
        if comp is None:
            return self._drop(row, "company_not_resolved")
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

    def _party_named_in(self, line: str):
        names = [p for p in self.reg.parties.values() if p.kind == "legal_entity" and name_full_on(p.name, line)]
        return max(names, key=lambda p: len(p.name)) if names else None

    def _resolve_company(self, company, holder, units, ref, own):
        """Which company a holding row is about: the model's answer when the text supports it, otherwise the
        holding already read on the same line, otherwise the company named at the head of the register."""
        doc = self.docs[ref.doc]
        owner_line = register_owner(doc, ref)
        if company:
            credible = name_full_on(company, own) or owner_line is None or name_full_on(company, owner_line)
            if credible:
                comp = self.reg.find(company) or self._target_alias(company)
                if comp is not None:
                    return comp
                if _entity(company) and name_full_on(company, self._context(ref, 40)):
                    return self.reg.get_or_create(company, ref, "legal_entity")
        hid = self.reg.find(holder)
        same = next((x for x in self.holdings if hid and x.holder == hid.id and x.units_held == units
                     and x.ref and (x.ref.doc, x.ref.page, x.ref.line) == (ref.doc, ref.page, ref.line)), None)
        if same is not None:
            return self.reg.parties[same.company]
        return self._party_named_in(owner_line) if owner_line else None

    def _target_alias(self, name: str):
        if self.target_name and normalise(name) and normalise(name) in normalise(self.target_name):
            return self.reg.find(self.target_name)
        return None

    def _agreements(self, row, ref, ctx):
        kind, controller, controlled, company = row.values
        wide = self._context(ref, 2)
        if not AGREEMENT_EVIDENCE.search(fold(wide)):
            return self._drop(row, "no_agreement_wording")
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
        line = self.docs[ref.doc].line(ref.page, ref.line) or ""
        # company: only if written next to the role; a role line without a company refers to the document's company
        comp = None
        if company and name_full_on(company, ctx):
            comp = self.reg.find(company) or self._target_alias(company)
        if comp is None:
            comp = self._party_named_in(line)
        # role: as written on the line; a translated or invented role is replaced by the line's own wording
        if not role_raw or not name_on(role_raw, ctx):
            role_raw = line
        self.board.append(BoardRole(p.id, comp.id if comp else None, role_raw, normalise_role(role_raw), ref))

    def _persons(self, row, ref, ctx):
        name, birth, nationality, residence = row.values
        if not name or not name_on(name, ctx) or _entity(name):
            return self._drop(row, "name_not_on_line")
        p = self.reg.get_or_create(name, ref, "natural_person")
        for key, val in (("birth_date", birth), ("nationality", nationality), ("residence", residence)):
            if val and key not in p.fields:
                if name_on(val, ctx) or any(n in numbers_on(ctx) for n in numbers_on(val)):
                    p.fields[key] = Field(val, ref)

    def _confirm_missing_totals(self, holdings: list[Holding]) -> None:
        """Cross-check, not extraction: when the model gave no total for a company, accept the sum of the
        holdings read for it only if that very number is written on a capital line of the same document."""
        by_company: dict[str, list[Holding]] = {}
        for h in holdings:
            if h.units_held and h.basis in ("capital", "both"):
                by_company.setdefault(h.company, []).append(h)
        for comp, hs in by_company.items():
            party = self.reg.parties[comp]
            if party.total_capital is not None:
                continue
            total = sum(h.units_held for h in hs)
            for doc_id in {h.ref.doc for h in hs if h.ref}:
                doc = self.docs[doc_id]
                hit = next((LineRef(doc_id, p.number, i) for p in doc.pages for i, line in enumerate(p.lines, 1)
                            if CAPITAL_LINE.search(line) and total in numbers_on(line)), None)
                if hit:
                    party.total_capital, party.total_ref = total, hit
                    self.accepted["total_confirmed_by_register_sum"] += 1
                    break

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
        # (the version that names a principal wins; identical lots on different lines are merged, see report)
        merged: dict[tuple, Holding] = {}
        for h in self.holdings:
            key = (h.holder, h.company, h.units_held, h.written_percent)
            kept = merged.get(key)
            if kept is None:
                merged[key] = h
            elif h.held_for and not kept.held_for:
                kept.held_for = h.held_for
        unique = list(merged.values())
        self._confirm_missing_totals(unique)
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
