from beneficia.rules.engine import analyse
from beneficia.rules.fallback import normalise_role
from tests.helpers import company, facts, person

FIVE = [person(f"p{i}") for i in range(5)]
SPREAD = [(f"p{i}", "t", 20) for i in range(5)]


def test_nobody_qualifies_proposes_board_chair_pending_review():
    f = facts("t", [company("t"), *FIVE, person("chair")], SPREAD,
              board=[("chair", "t", "Präsident des Verwaltungsrates", "chair"),
                     ("p1", "t", "Mitglied", "member")])
    r = analyse(f)
    assert len(r.findings) == 1
    fd = r.findings[0]
    assert fd.person == "chair" and fd.basis == "default_manager"
    assert fd.status == "pending_review"
    assert "TJPG art. 4 para. 2" in fd.articles
    assert any(i.reason == "default_manager" for i in r.review)


def test_sole_managing_officer_of_gmbh():
    f = facts("t", [company("t"), *FIVE, person("g")], SPREAD,
              board=[("g", "t", "gérant unique", "sole_officer")])
    assert analyse(f).findings[0].person == "g"


def test_ambiguous_managing_body_proposes_nobody():
    f = facts("t", [company("t"), *FIVE, person("m1"), person("m2")], SPREAD,
              board=[("m1", "t", "Mitglied", "member"), ("m2", "t", "Mitglied", "member")])
    r = analyse(f)
    assert r.findings == []
    assert any(i.reason == "default_manager_unclear" for i in r.review)


def test_default_rule_not_used_when_someone_qualifies():
    f = facts("t", [company("t"), person("a"), person("b"), person("chair")], [("a", "t", 60), ("b", "t", 40)],
              board=[("chair", "t", "Präsident", "chair")])
    assert all(x.basis != "default_manager" for x in analyse(f).findings)


def test_role_normalisation_three_languages():
    assert normalise_role("Präsident des Verwaltungsrates") == "chair"
    assert normalise_role("Président du conseil d'administration") == "chair"
    assert normalise_role("Presidente del consiglio di amministrazione") == "chair"
    assert normalise_role("Vorsitzender der Geschäftsführung") == "chair"
    assert normalise_role("Gesellschafter und Geschäftsführer") == "managing_officer"
    assert normalise_role("gérant") == "managing_officer"
    assert normalise_role("amministratore unico") == "sole_officer"
    assert normalise_role("einziges Mitglied des Verwaltungsrates") == "sole_officer"
    assert normalise_role("membre") == "member"
