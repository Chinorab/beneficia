"""OCR with Tesseract (deu, fra, ita). The Apertus GGUF is text only, so scans go through OCR."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from beneficia.ingest.lines import clean_lines
from beneficia.model import Page

LANGS = "deu+fra+ita"
LOW_CONFIDENCE = 70.0


def available() -> bool:
    return shutil.which("tesseract") is not None


def ocr_image(image, number: int) -> Page:
    import pytesseract

    data = pytesseract.image_to_data(image, lang=LANGS, config="--psm 6",
                                     output_type=pytesseract.Output.DICT)
    rows: dict[tuple[int, int, int], list[str]] = {}
    confs = []
    for i, word in enumerate(data["text"]):
        if not word.strip():
            continue
        conf = float(data["conf"][i])
        if conf >= 0:
            confs.append(conf)
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        rows.setdefault(key, []).append(word)
    lines = clean_lines("\n".join(" ".join(ws) for _, ws in sorted(rows.items())))
    mean = sum(confs) / len(confs) if confs else 0.0
    return Page(number, lines, round(mean, 1))


def ocr_image_file(path: Path) -> list[Page]:
    from PIL import Image, ImageSequence

    with Image.open(path) as im:
        return [ocr_image(frame.convert("L"), i + 1) for i, frame in enumerate(ImageSequence.Iterator(im))]


def ocr_pdf_page(path: Path, number: int, dpi: int = 300) -> Page:
    from PIL import Image

    with tempfile.TemporaryDirectory() as tmp:
        stem = Path(tmp) / "p"
        subprocess.run(["pdftoppm", "-r", str(dpi), "-gray", "-png", "-f", str(number), "-l", str(number),
                        "-singlefile", str(path), str(stem)], check=True, capture_output=True)
        with Image.open(str(stem) + ".png") as im:
            return ocr_image(im.copy(), number)
