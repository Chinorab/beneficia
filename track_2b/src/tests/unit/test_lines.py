from beneficia.ingest.lines import detect_language, numbered_windows, pages_from_text
from beneficia.model import Document, LineRef


def test_page_markers_and_preamble():
    pages = pages_from_text("[TEST]\nSeite 1\na\n\nb\nSeite 2\nc\n")
    assert [p.lines for p in pages] == [["[TEST]", "a", "b"], ["c"]]


def test_form_feed_splits_pages():
    assert len(pages_from_text("a\fb\fc")) == 3


def test_windows_cover_all_lines_with_overlap():
    doc = Document("D1", "x.txt", "txt", pages_from_text("\n".join(f"l{i}" for i in range(130))))
    wins = list(numbered_windows(doc, size=60, overlap=5))
    ids = [i for _, w in wins for i in w]
    assert ids[0] == "P1.L1" and "P1.L130" in ids and len(wins) == 3


def test_ref_roundtrip_and_language():
    assert str(LineRef.parse("D2.P1.L7")) == "D2.P1.L7"
    assert detect_language(["Die Gesellschaft und der Aktionär mit den Aktien ist"]) == "de"
    assert detect_language(["La société et les actions du capital est"]) == "fr"
    assert detect_language(["Il capitale della società è diviso in azioni di"]) == "it"
