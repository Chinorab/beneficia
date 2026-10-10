from beneficia.rules.engine import analyse
from tests.helpers import company, facts, person


def settled(result):
    return {f.person: f for f in result.findings if f.status == "settled"}


def test_exactly_25_percent_qualifies_directly():
    r = analyse(facts("t", [company("t", 100), person("a"), person("b")], [("a", "t", 25), ("b", "t", 75)]))
    s = settled(r)
    assert set(s) == {"a", "b"}
    assert s["a"].basis == "direct"
    assert "TJPV art. 1" in s["a"].articles


def test_just_below_25_percent_does_not_qualify():
    r = analyse(facts("t", [company("t", 10000), person("a"), person("b")],
                      [("a", "t", 2499), ("b", "t", 7501)]))
    assert set(settled(r)) == {"b"}


def test_votes_alone_qualify():
    f = facts("t", [company("t", 100, votes=1000), person("a"), person("b")],
              [("a", "t", 5, "capital"), ("a", "t", 300, "votes"),
               ("b", "t", 95, "capital"), ("b", "t", 700, "votes")])
    s = settled(analyse(f))
    assert set(s) == {"a", "b"}


def test_legal_entity_never_listed_as_beneficial_owner():
    r = analyse(facts("t", [company("t"), company("x"), person("a")], [("x", "t", 100), ("a", "x", 100)]))
    assert all(f.person != "x" for f in r.findings)
