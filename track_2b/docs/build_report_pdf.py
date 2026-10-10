"""Render technical_report.md to Beneficia_Report.pdf (A4) with a headless Chromium browser.

Usage: python docs/build_report_pdf.py [path/to/chrome]
Needs the `markdown` and `pypdf` packages. Fails if the PDF exceeds 6 pages (submission rule).
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
CSS = """
@page { size: A4; margin: 16mm 15mm 16mm 15mm; }
body { font: 9.6pt/1.42 "IBM Plex Sans", "Segoe UI", Arial, sans-serif; color: #16191c; }
h1 { font-size: 17pt; margin: 0 0 6pt; } h2 { font-size: 12pt; margin: 12pt 0 4pt; border-bottom: 1px solid #c9ced3; padding-bottom: 2pt; }
h3 { font-size: 10.5pt; margin: 8pt 0 3pt; } p, li { margin: 3pt 0; } ul { padding-left: 14pt; margin: 3pt 0; }
code { font: 8.4pt "IBM Plex Mono", Consolas, monospace; background: #eef0f2; padding: 0 2px; }
pre { font: 7.6pt/1.25 "IBM Plex Mono", Consolas, monospace; background: #f4f5f6; border: 1px solid #d5d9dd; padding: 6pt; white-space: pre; overflow: hidden; }
pre code { background: none; padding: 0; font-size: inherit; }
table { border-collapse: collapse; width: 100%; margin: 5pt 0; font-size: 8.6pt; }
th, td { border: 1px solid #d5d9dd; padding: 2.5pt 4pt; text-align: left; vertical-align: top; }
th { background: #eceef0; } a { color: #0f5c63; text-decoration: none; }
img { max-width: 100%; }
"""


def main() -> None:
    chrome = sys.argv[1] if len(sys.argv) > 1 else (
        shutil.which("chromium") or shutil.which("google-chrome") or shutil.which("chrome")
        or r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe")
    md = (ROOT / "technical_report.md").read_text(encoding="utf-8")
    # Python-Markdown needs four spaces for nested lists; the report uses two (GitHub style)
    md = re.sub(r"(?m)^  (  )?([-*] |\d+\. )", lambda m: "    " * (1 + bool(m.group(1))) + m.group(2), md)
    # ... and a blank line before a list that follows a paragraph line
    md = re.sub(r"(?m)^((?![ \t]*(?:[-*] |\d+\. |\|))[^\n]*\S)\n([-*] |\d+\. )", r"\1\n\n\2", md)
    html = markdown.markdown(md, extensions=["tables", "fenced_code"])
    page = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{html}</body></html>"
    out = ROOT / "Beneficia_Report.pdf"
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "report.html"
        src.write_text(page, encoding="utf-8")
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={out}", src.as_uri()], check=True, capture_output=True, timeout=120)
    pages = len(PdfReader(str(out)).pages)
    print(f"{out.name}: {pages} pages")
    if pages > 6:
        sys.exit("report exceeds 6 pages")


if __name__ == "__main__":
    main()
