"""Name normalisation and party registry."""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

from beneficia.model import LineRef, Party

HONORIFICS = {"herr", "frau", "hr", "fr", "dr", "prof", "m", "mme", "mlle", "monsieur", "madame", "me",
              "sig", "sigra", "signor", "signora", "dott", "avv"}
LEGAL_FORMS = [
    (r"\bs\.?\s?a\.?\s?r\.?\s?l\.?\b|\bsarl\b", "sarl"), (r"\bs\.?\s?a\.?\s?g\.?\s?l\.?\b|\bsagl\b", "sagl"),
    (r"\bs\.?\s?p\.?\s?a\.?\b", "spa"), (r"\bs\.?\s?r\.?\s?l\.?\b", "srl"), (r"\bs\.?\s?a\.?\b", "sa"),
    (r"\bgmbh\b", "gmbh"), (r"\bag\b", "ag"), (r"\bltd\.?\b|\blimited\b", "ltd"), (r"\binc\.?\b", "inc"),
]
ENTITY_HINTS = re.compile(
    r"\b(ag|sa|gmbh|sarl|sagl|spa|srl|ltd|inc|llc|bv|nv|plc|kg|holding|stiftung|fondation|fondazione|verein|"
    r"association|associazione|genossenschaft|cooperative|cooperativa|trust|fiduciaire|treuhand|"
    r"beteiligungen|participations|partecipazioni|group|gruppe|groupe|corp)\b")
SPECIAL = [
    (re.compile(r"\b(stiftung|fondation|fondazione|foundation)\b"), "foundation"),
    (re.compile(r"\b(verein|association|associazione)\b"), "association"),
    (re.compile(r"\btrust\b"), "trust"),
    (re.compile(r"\b(pensionskasse|caisse de pension|cassa pensione|vorsorge|prevoyance|previdenza)\b"), "pension"),
    (re.compile(r"\b(anlagefonds|fonds de placement|fondo d'investimento)\b"), "fund"),
]


def fold(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def normalise(name: str) -> str:
    t = fold(name).replace("’", "'")
    for pattern, repl in LEGAL_FORMS:
        t = re.sub(pattern, repl, t)
    t = re.sub(r"[^\w\s]", " ", t)
    return " ".join(w for w in t.split() if w not in HONORIFICS)


def match_key(name: str) -> str:
    """Order-insensitive key so 'Imhof Petra' and 'Petra Imhof' match."""
    return " ".join(sorted(normalise(name).split()))


def looks_like_entity(name: str) -> bool:
    return bool(ENTITY_HINTS.search(normalise(name)))


def special_kind(name: str) -> Optional[str]:
    n = fold(name)
    for pattern, kind in SPECIAL:
        if pattern.search(n):
            return kind
    return None


def slug(name: str) -> str:
    return re.sub(r"\s+", "_", normalise(name)) or "unnamed"


class PartyRegistry:
    def __init__(self) -> None:
        self.parties: dict[str, Party] = {}
        self._by_key: dict[str, str] = {}

    def find(self, name: str) -> Optional[Party]:
        if not name:
            return None
        pid = self._by_key.get(match_key(name))
        return self.parties.get(pid) if pid else None

    def get_or_create(self, name: str, ref: Optional[LineRef], kind: Optional[str] = None) -> Party:
        existing = self.find(name)
        if existing is not None:
            if ref and ref not in existing.refs:
                existing.refs.append(ref)
            if kind == "legal_entity" and existing.kind != "legal_entity":
                existing.kind = "legal_entity"
            return existing
        kind = kind or ("legal_entity" if looks_like_entity(name) else "natural_person")
        pid = base = slug(name)
        n = 2
        while pid in self.parties:
            pid, n = f"{base}_{n}", n + 1
        party = Party(pid, kind, name.strip(), [ref] if ref else [])
        if kind == "legal_entity":
            party.special_kind = special_kind(name)
        self.parties[pid] = party
        self._by_key[match_key(name)] = pid
        return party
