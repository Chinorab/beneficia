from fractions import Fraction

from beneficia.rules.graph import OwnershipGraph
from tests.helpers import company, facts, person


def test_shares_are_exact_fractions_over_stated_total():
    f = facts("t", [company("t", 1000), person("a"), person("b")], [("a", "t", 520), ("b", "t", 480)])
    g = OwnershipGraph(f)
    assert g.share("a", "t", "capital") == Fraction(52, 100)
    assert g.share("a", "t", "votes") == Fraction(52, 100)
    assert g.share("b", "t", "capital") == Fraction(12, 25)


def test_multiple_lines_of_same_holder_are_aggregated():
    f = facts("t", [company("t", 100), person("a")], [("a", "t", 10), ("a", "t", 20)])
    assert OwnershipGraph(f).share("a", "t", "capital") == Fraction(30, 100)


def test_votes_differ_from_capital_with_vote_only_lines():
    # 100 capital units, 200 votes in total (voting shares); a holds 10 capital units carrying 120 votes
    f = facts("t", [company("t", 100, votes=200), person("a")],
              [("a", "t", 10, "capital"), ("a", "t", 120, "votes")])
    g = OwnershipGraph(f)
    assert g.share("a", "t", "capital") == Fraction(1, 10)
    assert g.share("a", "t", "votes") == Fraction(3, 5)


def test_unknown_total_falls_back_to_register_sum_and_is_marked():
    f = facts("t", [company("t", None), person("a"), person("b")], [("a", "t", 3), ("b", "t", 1)])
    g = OwnershipGraph(f)
    assert g.share("a", "t", "capital") == Fraction(3, 4)
    assert "t" in g.total_from_register_sum


def test_fiduciary_holding_is_attributed_to_principal():
    f = facts("t", [company("t", 100), company("nominee_sa"), person("p")],
              [("nominee_sa", "t", 40, "both", "p")])
    g = OwnershipGraph(f)
    assert g.share("p", "t", "capital") == Fraction(2, 5)
    assert g.share("nominee_sa", "t", "capital") == 0
    assert ("p", "t") in g.fiduciary_edges


def test_cycle_detection():
    f = facts("t", [company("t"), company("x"), company("y")],
              [("x", "t", 50), ("y", "x", 60), ("x", "y", 60)])
    assert OwnershipGraph(f).cycles()


def test_written_percentage_without_units_is_used_as_share():
    from fractions import Fraction as F
    from beneficia.model import Holding, LineRef
    f = facts("t", [company("t"), company("x", None), person("a"), person("k")], [("x", "t", 30), ("a", "t", 70)])
    f.holdings.append(Holding("k", "x", 0, "both", None, F(1), LineRef("D1", 2, 5)))
    g = OwnershipGraph(f)
    assert g.share("k", "x", "capital") == 1
    assert "k" in g.holders_of("x")
