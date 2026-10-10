"""Load a case folder into documents with ids D1, D2, ... in file name order."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from beneficia.ingest import ocr
from beneficia.ingest.lines import detect_language
from beneficia.ingest.pdf import read_pdf
from beneficia.ingest.text import read_docx, read_txt
from beneficia.model import Document

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
SKIP = {"case.json", "expected.json"}


@dataclass
class Case:
    id: str
    path: Path
    target: Optional[str]
    documents: list[Document] = field(default_factory=list)

    @property
    def docs(self) -> dict[str, Document]:
        return {d.id: d for d in self.documents}


def load_document(path: Path, doc_id: str) -> Document:
    ext = path.suffix.lower()
    doc = Document(doc_id, path.name, "txt")
    try:
        if ext == ".txt":
            doc.pages = read_txt(path)
        elif ext == ".docx":
            doc.kind, doc.pages = "docx", read_docx(path)
        elif ext == ".pdf":
            doc.pages, used_ocr = read_pdf(path)
            doc.kind = "pdf_scan" if used_ocr else "pdf_text"
        elif ext in IMAGE_EXT:
            doc.kind = "image"
            if not ocr.available():
                raise RuntimeError("OCR engine not installed")
            doc.pages = ocr.ocr_image_file(path)
        else:
            raise ValueError(f"unsupported file type {ext}")
    except Exception as exc:  # unreadable file: reported, analysis continues
        doc.readable, doc.error, doc.pages = False, str(exc)[:200], []
    if doc.readable and not any(p.lines for p in doc.pages):
        doc.readable, doc.error = False, "no text found"
    doc.language = detect_language([line for p in doc.pages for line in p.lines])
    return doc


def load_case(path: Path) -> Case:
    meta = {}
    if (path / "case.json").exists():
        meta = json.loads((path / "case.json").read_text(encoding="utf-8"))
    files = sorted(p for p in path.iterdir() if p.is_file() and p.name not in SKIP and not p.name.startswith("."))
    docs = [load_document(p, f"D{i}") for i, p in enumerate(files, 1)]
    return Case(path.name, path, meta.get("target"), docs)
