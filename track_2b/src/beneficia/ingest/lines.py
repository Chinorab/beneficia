"""Numbered lines: the single reference text for every citation (constitution principle III)."""
from __future__ import annotations

import re
from typing import Iterable, Optional

from beneficia.model import Document, LineRef, Page

_WS = re.compile(r"[ \t ]+")
PAGE_MARKER = re.compile(r"^\s*(Seite|Page|Pagina)\s+(\d+)\s*$", re.IGNORECASE)


def clean_lines(text: str) -> list[str]:
    out = []
    for raw in text.splitlines():
        line = _WS.sub(" ", raw).strip()
        if line:
            out.append(line)
    return out


def pages_from_text(text: str) -> list[Page]:
    """Split on form feeds; inside a chunk, a line 'Seite N' / 'Page N' / 'Pagina N' also starts a page."""
    pages: list[Page] = []
    for chunk in text.split("\f"):
        current: list[str] = []
        started = False
        for line in clean_lines(chunk):
            if PAGE_MARKER.match(line):
                if started and current:
                    pages.append(Page(len(pages) + 1, current))
                    current = []
                started = True  # lines before the first marker stay on the first page
                continue
            current.append(line)
        if current:
            pages.append(Page(len(pages) + 1, current))
    return pages or [Page(1, [])]


def resolve(docs: dict[str, Document], ref: LineRef) -> Optional[str]:
    doc = docs.get(ref.doc)
    return doc.line(ref.page, ref.line) if doc else None


def numbered_windows(doc: Document, size: int = 60, overlap: int = 5) -> Iterable[tuple[str, list[str]]]:
    """Yield (prompt text, ids in window) with ids 'P<page>.L<line>' (document id added by code)."""
    flat = [(f"P{p.number}.L{i}", text) for p in doc.pages for i, text in enumerate(p.lines, 1)]
    if not flat:
        return
    step = max(1, size - overlap)
    start = 0
    while start < len(flat):
        window = flat[start:start + size]
        yield "\n".join(f"{lid} {text}" for lid, text in window), [lid for lid, _ in window]
        if start + size >= len(flat):
            break
        start += step


def detect_language(lines: list[str]) -> str:
    words = re.findall(r"[a-zàâäéèêëîïôöùûüç']+", " ".join(lines).lower())
    sets = {
        "de": {"der", "die", "das", "und", "mit", "von", "des", "aktien", "gesellschaft", "ist", "zu"},
        "fr": {"le", "la", "les", "des", "du", "et", "de", "actions", "société", "est", "à"},
        "it": {"il", "lo", "la", "gli", "delle", "della", "e", "di", "azioni", "società", "è"},
    }
    scores = {k: sum(1 for w in words if w in v) for k, v in sets.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] >= 3 else "unknown"
