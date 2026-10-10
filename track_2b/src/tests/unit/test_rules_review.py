from beneficia.model import Field, LineRef
from beneficia.rules.engine import analyse
from tests.helpers import company, facts, person


def by_person(r):
    return {f.person: f for f in r.findings}


def reasons(r):
    return {i.reason for i in r.review}


def test_voting_pact_on_qualified_holder_is_listed_but_not_changed():
    f = facts("t", [company("t", 1000), person("imhof"), person("ammann"), company("berg")],
              [("imhof", "t", 520), ("berg", "t", 300), ("ammann", "t", 180)],
              agreements=[("voting", "imhof", "ammann", "t")])
    r = analyse(f)
    assert by_person(r)["imhof"].status == "settled"
    assert "concert" in reasons(r)


def test_voting_pact_creates_pending_candidate_with_combined_votes():
    f = facts("t", [company("t"), person("a"), person("b"), person("c")],
              [("a", "t", 15), ("b", "t", 15), ("c", "t", 70)],
              agreements=[("voting", "a", "b", "t")])
    r = analyse(f)
    cand = by_person(r)["a"]
    assert cand.status == "pending_review" and cand.basis == "other_means"
    assert cand.control_type["alone_or_concert"] == "concert"
    assert cand.band == "25_50"
    assert "TJPV art. 4" in cand.articles


def test_fiduciary_holding_principal_is_pending_and_nominee_never_proposed():
    f = facts("t", [company("t", 200), company("fid_sa"), person("berger"), person("rochat")],
              [("rochat", "t", 120), ("fid_sa", "t", 80, "both", "berger")])
    r = analyse(f)
    p = by_person(r)
    assert p["berger"].status == "pending_review"
    assert p["berger"].chain_info_required is True
    assert "fid_sa" not in p
    assert "fiduciary" in reasons(r)
    assert p["rochat"].status == "settled"


def test_undocumented_entity_holder_requests_ownership_proof():
    f = facts("t", [company("t"), company("offshore_ltd", foreign=True), person("a")],
              [("offshore_ltd", "t", 60), ("a", "t", 40)])
    r = analyse(f)
    assert "foreign_or_undocumented" in reasons(r)
    assert any(m.what == "ownership_proof" and m.about == "offshore_ltd" for m in r.missing)


def test_small_undocumented_entity_is_not_flagged():
    f = facts("t", [company("t"), company("tiny"), person("a")], [("tiny", "t", 10), ("a", "t", 90)])
    assert "foreign_or_undocumented" not in reasons(analyse(f))


def test_special_holder_is_flagged_with_article():
    f = facts("t", [company("t"), company("stiftung_x", special_kind="foundation"), person("a")],
              [("stiftung_x", "t", 70), ("a", "t", 30)])
    r = analyse(f)
    items = [i for i in r.review if i.reason == "special_holder"]
    assert items and items[0].article == "TJPV art. 7"


def test_veto_right_creates_pending_other_means_candidate():
    f = facts("t", [company("t"), person("a"), person("b"), person("v")], [("a", "t", 50), ("b", "t", 50)],
              agreements=[("veto", "v", "t", "t")])
    r = analyse(f)
    assert by_person(r)["v"].status == "pending_review"
    assert "other_means" in reasons(r)


def test_low_ocr_turns_finding_pending():
    f = facts("t", [company("t", 1000), person("a"), person("b")], [("a", "t", 600), ("b", "t", 400)])
    f.low_confidence_refs = [f.holdings[0].ref]
    r = analyse(f)
    assert by_person(r)["a"].status == "pending_review"
    assert "low_ocr" in reasons(r)


def test_missing_identification_fields_are_requested():
    a = person("a")
    a.fields["birth_date"] = Field("12.03.1971", LineRef("D1", 1, 99))
    f = facts("t", [company("t"), a], [("a", "t", 100)])
    r = analyse(f)
    miss = [m for m in r.missing if m.what == "identification" and m.about == "a"]
    assert miss and miss[0].reason == "nationality,residence"


def test_fiduciary_holding_without_control_is_still_reviewed():
    f = facts("t", [company("t", 200), company("fid_sa"), person("berger"), person("rochat")],
              [("rochat", "t", 160), ("fid_sa", "t", 40, "both", "berger")])
    r = analyse(f)
    assert "berger" not in by_person(r)
    items = [i for i in r.review if i.reason == "fiduciary"]
    assert items and set(items[0].parties) == {"berger", "fid_sa"}
