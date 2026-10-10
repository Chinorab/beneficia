"""Five narrow extraction passes (see contracts/extraction-passes.md).

The model only copies what is written. Every row ends with the id of the line it comes from; the JSON
schema restricts that id to the ids present in the window, so a citation can never point outside it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Callable

from beneficia.ingest.lines import numbered_windows
from beneficia.model import Document

COMMON = (
    "You read Swiss corporate documents written in German, French or Italian. Each input line starts "
    "with an id like P1.L7. Copy names and numbers exactly as written in the document. Never compute, "
    "convert or round anything. Use null when a value is not written. List only what the document says. "
    "Every row ends with the id of the line where the fact is written. If nothing matches, return an "
    "empty list."
)

STR = {"type": "string"}
NSTR = {"type": ["string", "null"]}
NINT = {"type": ["integer", "null"]}
NNUM = {"type": ["number", "null"]}


@dataclass(frozen=True)
class Pass:
    name: str
    key: str
    instruction: str
    columns: tuple[dict, ...]
    keywords: tuple[str, ...]  # window is sent only if one keyword appears (empty: always)
    max_tokens: int = 500
    example: tuple[str, str] | None = None  # invented one-shot example (user text, expected JSON)
    line_filter: Callable[[str], bool] | None = None  # send only matching lines of the window
    skip_covered: bool = False  # drop lines already cited by an earlier holdings pass

    def schema(self, line_ids: list[str]) -> dict:
        row = {"type": "array", "prefixItems": [*self.columns, {"enum": line_ids}],
               "minItems": len(self.columns) + 1, "maxItems": len(self.columns) + 1}
        return {"type": "object", "properties": {self.key: {"type": "array", "items": row}},
                "required": [self.key], "additionalProperties": False}

    def system(self) -> str:
        return COMMON + " " + self.instruction


SHARE_WORDS = ("aktie", "stammanteil", "anteil", "stimmrecht", "kapital", "action", "part", "capital",
               "droit de vote", "azion", "quota", "capitale", "diritt", "%", "gesellschafter", "associ")

PASSES: tuple[Pass, ...] = (
    Pass("companies", "c",
         "List every company named in the document (AG, SA, GmbH, Sarl, Sagl, Ltd and similar legal "
         "entities). Never list a natural person here. Output {\"c\": [[name, legal_form, seat, total_units, "
         "unit_kind, line_id], ...]}. total_units is the total number of shares or quotas into which the "
         "company's capital is divided, only if written (for example 'divided into 1'000 registered shares' "
         "gives 1000); it is never the number held by one shareholder. unit_kind is shares, quotas or votes. "
         "line_id is the line with total_units if any, else the line naming the company.",
         (STR, NSTR, NSTR, NINT, {"enum": ["shares", "quotas", "votes", None]}), ()),
    Pass("holdings", "h",
         "List every holding of shares, quotas or voting rights written in the document: who holds how many "
         "units of which company. Output {\"h\": [[holder, company, units_held, percent_written, held_for, "
         "basis, line_id], ...]}. units_held is the number of shares or quotas held, null if only a percentage "
         "is written. percent_written is a percentage only if it is literally written for this holding, else "
         "null. held_for is the person on whose behalf the units are held (fiduciary, nominee), else null. "
         "basis is capital, votes or both (both when shares carry one vote each or nothing else is said). "
         "Sentences also count, for example 'the sole shareholder of Y is X', 'Y belongs 100 % to X', "
         "'X detient 40 % de Y'. Do not list the total share capital, addresses or board roles as holdings.",
         (STR, STR, NINT, NNUM, NSTR, {"enum": ["capital", "votes", "both", None]}), SHARE_WORDS),
    Pass("agreements", "a",
         "List agreements or clauses that give a person control over a company other than by holding "
         "shares: voting agreements (one shareholder must vote as another person instructs), fiduciary "
         "arrangements, veto rights, rights to appoint or remove board members. Output {\"a\": [[kind, "
         "controller, controlled, company, line_id], ...]}. kind is voting, fiduciary, veto, appointment or "
         "other. controller is the person who gains control, controlled is the party bound by it.",
         ({"enum": ["voting", "fiduciary", "veto", "appointment", "other"]}, STR, STR, NSTR),
         ("stimm", "vote", "voto", "bindung", "pacte", "patto", "convention", "vertrag", "accord", "treuh",
          "fiduci", "veto", "ernenn", "nommer", "nominare", "weisung", "instruction", "istruzion", "abberuf",
          "révoqu", "revoc")),
    Pass("board", "b",
         "List members of the board of directors or the management of each company. Output {\"b\": [[person, "
         "company, role_as_written, line_id], ...]}. role_as_written is copied exactly (for example "
         "'Präsident des Verwaltungsrates', 'gérant', 'presidente').",
         (STR, NSTR, STR),
         ("verwaltungsrat", "präsident", "prasident", "geschäftsführ", "geschaftsfuhr", "vorsitz", "mitglied",
          "conseil", "président", "president", "administrat", "gérant", "gerant", "direct", "consiglio",
          "amministrat", "gerente", "organ")),
    Pass("persons", "p",
         "List every natural person (human being, not a company) with the identification data written next "
         "to the name. Output {\"p\": [[name, birth_date, nationality, residence, line_id], ...]}. birth_date, "
         "nationality and residence (municipality, postal code, country) are copied as written, else null.",
         (STR, NSTR, NSTR, NSTR),
         ("geb", "né", "nee", "nato", "nata", "bürger", "burger", "national", "staatsang", "wohn", "domicil",
          "residen", "cittadin", "heimatort", "originaire", "attinen", "19", "20")),
)


PROSE_HOLDING = re.compile(
    r"(%|prozent|pour ?cent|per ?cento|gehört|gehoert|hält|haelt|détient|detient|détenu|appartient|appartiene|"
    r"detiene|alleinig|einzig|sole |unique|unico|unica|gesellschafter|associé|associe|actionnaire|aktionär|"
    r"socio|azionista|treuhänderisch|fiduciaire|fiduciari)", re.IGNORECASE)


def _is_prose_holding(line: str) -> bool:
    return line.count("|") < 2 and bool(PROSE_HOLDING.search(line))


PROSE_EXAMPLE = (
    "\n".join([
        "P1.L4 The sole partner of Holz Invest GmbH is Max Test, Thun.",
        "P1.L5 Treuhand Muster AG holds 20 quotas of Holz Invest GmbH for Lea Fiktiv.",
        "P1.L7 Muster Beispiel AG appartient a 35 % a Nora Exempel."]),
    '{"h": [["Max Test", "Holz Invest GmbH", null, 100, null, "both", "P1.L4"], '
    '["Treuhand Muster AG", "Holz Invest GmbH", 20, null, "Lea Fiktiv", "both", "P1.L5"], '
    '["Nora Exempel", "Muster Beispiel AG", null, 35, null, "both", "P1.L7"]]}')

UNIT_WORDS = r"(aktien|namenaktien|stammanteile?|anteile?|actions?|parts?(?: sociales)?|azioni|quote|shares|quotas)"
REGISTER_ROW = re.compile(r"(\d[\d'’ ]*\s*" + UNIT_WORDS + r"\b|\d[\d'’]*\s*$)", re.IGNORECASE)
CAPITAL_LINE = re.compile(r"(eingeteilt|aktienkapital|stammkapital|divis|capital|suddivis|capitale|insgesamt|total)",
                          re.IGNORECASE)
ENDS_WITH_YEAR = re.compile(r"\b(19|20)\d{2}\.?\s*$")


def _is_register_row(line: str) -> bool:
    """A line that looks like 'name ... number [units]' but is not the total capital or a date."""
    if CAPITAL_LINE.search(line) or not REGISTER_ROW.search(line):
        return False
    if ENDS_WITH_YEAR.search(line) and not re.search(UNIT_WORDS, line, re.IGNORECASE):
        return False  # 'Stand per 30. September 2026'
    return bool(re.search(r"[A-Za-zÀ-ÿ]{3,}", line))


_holdings = next(p for p in PASSES if p.name == "holdings")
PASSES = PASSES[:2] + (
    replace(_holdings, name="holdings_prose", keywords=(), line_filter=_is_prose_holding, example=PROSE_EXAMPLE),
    replace(_holdings, name="holdings_retry", keywords=(), line_filter=_is_register_row, skip_covered=True),
) + PASSES[2:]


def merge_continuations(numbered: list[str]) -> list[str]:
    """Join a line that does not end a sentence with the next one, under the first line's id.

    Line wraps split sentences ('... pour le compte de' / 'Thomas Berger : 80 parts'); the resolver checks
    the cited line together with its neighbours, so the merged text stays verifiable."""
    out: list[str] = []
    i = 0
    while i < len(numbered):
        line = numbered[i]
        if i + 1 < len(numbered) and not line.rstrip().endswith((".", ":", ";", "!", "?")):
            nxt = numbered[i + 1].split(" ", 1)
            line = line + " " + (nxt[1] if len(nxt) > 1 else "")
            i += 1
        out.append(line)
        i += 1
    return out


@dataclass
class RawRow:
    pass_name: str
    doc: str
    values: list
    line_id: str  # P<page>.L<line>


def _wants(p: Pass, window_text: str) -> bool:
    if not p.keywords:
        return True
    low = window_text.lower()
    return any(k in low for k in p.keywords)


def run_passes(doc: Document, complete: Callable[..., dict],
               progress: Callable[[str], None] | None = None, log: list | None = None) -> list[RawRow]:
    rows: list[RawRow] = []
    windows = list(numbered_windows(doc))
    for p in PASSES:
        for wi, (text, ids) in enumerate(windows):
            if p.line_filter is not None:
                merged = merge_continuations(text.splitlines())
                kept = [ln for ln in merged if p.line_filter(ln.split(" ", 1)[1] if " " in ln else "")]
                if p.skip_covered:
                    covered = {r.line_id for r in rows if r.pass_name.startswith("holdings")}
                    kept = [ln for ln in kept if ln.split(" ", 1)[0] not in covered]
                if not kept:
                    continue
                text, ids = "\n".join(kept), [ln.split(" ", 1)[0] for ln in kept]
            if not _wants(p, text):
                continue
            if progress:
                progress(f"{doc.id}:{p.name}:{wi + 1}/{len(windows)}")
            out = complete(p.system(), text, p.schema(ids), p.max_tokens, p.example)
            if log is not None:
                log.append({"doc": doc.id, "pass": p.name, "window": wi + 1, "first_line": ids[0],
                            "last_line": ids[-1], "output": out})
            for row in out.get(p.key, []) if isinstance(out, dict) else []:
                if not isinstance(row, list) or len(row) != len(p.columns) + 1:
                    continue
                line_id = row[-1]
                if not isinstance(line_id, str) or not re.match(r"^P\d+\.L\d+$", line_id) or line_id not in ids:
                    continue
                rows.append(RawRow(p.name, doc.id, row[:-1], line_id))
    return rows
