"""PDF ingestion: text layer per page, OCR for pages without text."""
from __future__ import annotations

from pathlib import Path

from beneficia.ingest import ocr
from beneficia.ingest.lines import clean_lines
from beneficia.model import Page

MIN_TEXT_CHARS = 20


def read_pdf(path: Path) -> tuple[list[Page], bool]:
    """Return (pages, used_ocr)."""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages: list[Page] = []
    used_ocr = False
    for i, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        if len(text.strip()) >= MIN_TEXT_CHARS:
            pages.append(Page(i, clean_lines(text)))
        elif ocr.available():
            pages.append(ocr.ocr_pdf_page(path, i))
            used_ocr = True
        else:
            pages.append(Page(i, [], 0.0))
            used_ocr = True
    return pages, used_ocr
