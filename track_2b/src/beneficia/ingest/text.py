"""TXT and DOCX ingestion."""
from __future__ import annotations

from pathlib import Path

from beneficia.ingest.lines import clean_lines, pages_from_text
from beneficia.model import Page


def read_txt(path: Path) -> list[Page]:
    raw = path.read_bytes()
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return pages_from_text(raw.decode(enc))
        except UnicodeDecodeError:
            continue
    return pages_from_text(raw.decode("utf-8", errors="replace"))


def read_docx(path: Path) -> list[Page]:
    """Paragraphs and table rows in document order; explicit page breaks start a new page."""
    import docx
    from docx.oxml.ns import qn

    d = docx.Document(str(path))
    pages: list[list[str]] = [[]]
    body = d.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            text = "".join(t.text or "" for t in child.iter(qn("w:t")))
            pages[-1].extend(clean_lines(text))
            if any(br.get(qn("w:type")) == "page" for br in child.iter(qn("w:br"))):
                pages.append([])
        elif child.tag == qn("w:tbl"):
            for row in child.iter(qn("w:tr")):
                cells = []
                for cell in row.iter(qn("w:tc")):
                    cells.append(" ".join(clean_lines("".join(t.text or "" for t in cell.iter(qn("w:t"))))))
                line = " | ".join(c for c in cells)
                if line.strip(" |"):
                    pages[-1].append(line)
    return [Page(i + 1, lines) for i, lines in enumerate(p for p in pages if p)] or [Page(1, [])]
