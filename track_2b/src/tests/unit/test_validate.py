from beneficia.model import LineRef
from beneficia.rules.engine import analyse
from beneficia.validate import validate
from tests.helpers import company, facts, person


def test_consistent_register_passes():
    f = facts("t", [company("t", 1000), person("a"), person("b")], [("a", "t", 600), ("b", "t", 400)])
    assert validate(f) == []


def test_sum_mismatch_marks_company_and_findings_pending():
    f = facts("t", [company("t", 1000), person("a"), person("b")], [("a", "t", 600), ("b", "t", 300)])
    items = validate(f)
    assert items and items[0].detail["check"] == "sum_differs_from_total"
    r = analyse(f)
    assert all(x.status == "pending_review" for x in r.findings)


def test_holding_larger_than_total():
    f = facts("t", [company("t", 100), person("a")], [("a", "t", 150)])
    assert validate(f)[0].detail["check"] == "holding_exceeds_total"


def test_conflicting_totals_across_documents():
    f = facts("t", [company("t", 100), person("a")], [("a", "t", 100)])
    seen = {"t": [(100, "shares", LineRef("D1", 1, 1)), (1000, "shares", LineRef("D2", 1, 4))]}
    assert validate(f, seen)[0].detail["check"] == "conflicting_totals"
