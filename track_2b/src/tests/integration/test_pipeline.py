"""Full pipeline on a fictitious case with recorded Apertus outputs (no model needed)."""
import json
from pathlib import Path

from beneficia.extract.client import ReplayClient
from beneficia.pipeline import analyse_case

FIX = Path(__file__).resolve().parents[1] / "fixtures"


def run():
    responses = json.loads((FIX / "demo_de_responses.json").read_text(encoding="utf-8"))
    return analyse_case(FIX / "demo_de", ReplayClient(responses))


def test_demo_de_owners_and_review():
    r = run()
    found = {f["person"]: f for f in r["findings"]}
    assert found["petra_imhof"]["basis"] == "direct" and found["petra_imhof"]["band"] == "50_75"
    assert found["petra_imhof"]["status"] == "settled"
    keller = found["sandra_keller"]
    assert keller["basis"] == "indirect" and keller["band"] == "25_50"
    assert keller["chain"] == ["sandra_keller", "bergkristall_beteiligungen_gmbh", "alpenblick_holding_ag"]
    assert "concert" in {i["reason"] for i in r["review"]}


def test_every_reference_resolves_to_its_source_text():
    r = run()
    refs = set()
    for key in ("holdings", "agreements", "board"):
        refs |= {x["ref"] for x in r[key] if x["ref"]}
    for f in r["findings"] + r["review"]:
        refs |= set(f["refs"])
    assert refs and refs <= set(r["sources"])
    assert all(s["text"] for s in r["sources"].values())
