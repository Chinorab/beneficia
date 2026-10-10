"""Most senior member of the managing body (TJPG art. 4 para. 2)."""
from __future__ import annotations

import unicodedata
from typing import Optional

from beneficia.model import BoardRole


def _fold(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


SOLE = ("einzig", "allein", "unique", "seul ", "unico", "unica")
VICE = ("vize", "vice")
CHAIR = ("prasident", "president", "presidente", "vorsitz", "presidence", "presidenza")
OFFICER = ("geschaftsfuhrer", "gerant", "gerente", "directeur", "direttore", "geschaftsleiter",
           "amministratore delegato", "ceo")
MEMBER = ("mitglied", "membre", "membro", "administrateur", "amministratore", "verwaltungsrat")
BOARD_WORDS = ("verwaltungsrat", "conseil d'administration", "consiglio di amministrazione")


def normalise_role(raw: str) -> str:
    t = _fold(raw) + " "
    if any(w in t for w in SOLE):
        return "sole_officer"
    if any(w in t for w in VICE):
        return "member"
    if any(w in t for w in CHAIR):
        return "chair"
    if any(w in t for w in OFFICER):
        return "managing_officer"
    if any(w in t for w in MEMBER):
        return "member"
    return "other"


def most_senior(board: list[BoardRole], target: str) -> tuple[Optional[BoardRole], str]:
    """Return (role, reason). reason is 'ok' or 'unclear'."""
    roles = [b for b in board if b.company in (target, None)]
    for kind in ("sole_officer", "chair", "managing_officer"):
        cands = [b for b in roles if b.role == kind]
        persons = {b.person for b in cands}
        if len(persons) == 1:
            return cands[0], "ok"
        if len(persons) > 1:
            if kind == "chair":
                board_chairs = {b.person for b in cands if any(w in _fold(b.role_raw) for w in BOARD_WORDS)}
                if len(board_chairs) == 1:
                    pid = next(iter(board_chairs))
                    return next(b for b in cands if b.person == pid), "ok"
            return None, "unclear"
    return None, "unclear"
