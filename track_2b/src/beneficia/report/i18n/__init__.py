"""German and French strings. Quotes from documents are never translated."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

LANGS = ("de", "fr")
ABBR = {"de": {"TJPG": "TJPG", "TJPV": "TJPV"}, "fr": {"TJPG": "LTPM", "TJPV": "OTPM"}}


@lru_cache(maxsize=None)
def strings(lang: str) -> dict:
    lang = lang if lang in LANGS else "de"
    return json.loads((Path(__file__).parent / f"{lang}.json").read_text(encoding="utf-8"))


def t(lang: str, key: str) -> str:
    return strings(lang).get(key, strings("de").get(key, key))


def article(code: str, lang: str) -> str:
    """'TJPV art. 3 para. 2 let. e' -> 'Art. 3 Abs. 2 Bst. e TJPV' (de) or 'art. 3 al. 2 let. e OTPM' (fr)."""
    m = re.match(r"(TJPG|TJPV) art\. (.+)$", code)
    if not m:
        return code
    law, rest = m.groups()
    if lang == "fr":
        rest = rest.replace("para.", "al.").replace(" to ", " à ")
        return f"art. {rest} {ABBR['fr'][law]}"
    rest = rest.replace("para.", "Abs.").replace("let.", "Bst.").replace(" to ", " bis ")
    return f"Art. {rest} {law}"
