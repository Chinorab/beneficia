from beneficia.rules.engine import analyse
from tests.helpers import company, facts, person


def settled(result):
    return {f.person: f for f in result.findings if f.status == "settled"}


def test_majority_of_intermediate_holding_30_qualifies():
    f = facts("t", [company("t"), company("x"), person("a"), person("b"), person("c")],
              [("x", "t", 30), ("c", "t", 70), ("a", "x", 51), ("b", "x", 49)])
    s = settled(analyse(f))
    assert "a" in s and s["a"].basis == "indirect"
    assert s["a"].chain == ["a", "x", "t"]
    assert "TJPV art. 2" in s["a"].articles
    assert s["a"].band == "25_50"  # direct holding of the intermediate in the target (art. 13 para. 3)
    assert "b" not in s


def test_exactly_50_percent_of_intermediate_does_not_qualify():
    f = facts("t", [company("t"), company("x"), person("a"), person("b"), person("c")],
              [("x", "t", 100), ("a", "x", 50), ("b", "x", 50)])
    s = settled(analyse(f))
    assert "a" not in s and "b" not in s


def test_multiplication_trap_product_below_25_still_qualifies():
    # 60 % of x, x holds 40 % of t: product 24 %, but the ordinance looks at control of x
    f = facts("t", [company("t"), company("x"), person("a"), person("o"), person("c")],
              [("x", "t", 40), ("c", "t", 60), ("a", "x", 60), ("o", "x", 40)])
    assert "a" in settled(analyse(f))


def test_multiplication_trap_product_above_25_without_control_does_not_qualify():
    # 40 % of x, x holds 100 % of t: product 40 %, but no control of x
    f = facts("t", [company("t"), company("x"), person("a"), person("o")],
              [("x", "t", 100), ("a", "x", 40), ("o", "x", 60)])
    s = settled(analyse(f))
    assert "a" not in s
    assert "o" in s


def test_two_level_chain_and_chain_information():
    f = facts("t", [company("t"), company("x"), company("y"), person("a"), person("c")],
              [("x", "t", 80), ("c", "t", 20), ("y", "x", 70), ("a", "y", 90)])
    s = settled(analyse(f))
    assert s["a"].chain == ["a", "y", "x", "t"]
    assert s["a"].chain_info_required is True  # two intermediaries (TJPV art. 15)
    assert s["a"].band == "75_100"


def test_several_controlled_intermediates_are_aggregated():
    # a controls x (15 %) and y (15 %): together 30 % ("one or more intermediate entities")
    f = facts("t", [company("t"), company("x"), company("y"), person("a"), person("c")],
              [("x", "t", 15), ("y", "t", 15), ("c", "t", 70), ("a", "x", 100), ("a", "y", 100)])
    s = settled(analyse(f))
    assert s["a"].basis == "indirect"
    assert s["a"].band == "25_50"


def test_mixed_direct_and_indirect_goes_to_review():
    f = facts("t", [company("t"), company("x"), person("a"), person("c")],
              [("a", "t", 10), ("x", "t", 20), ("c", "t", 70), ("a", "x", 100)])
    r = analyse(f)
    assert "a" not in settled(r)
    pending = [x for x in r.findings if x.person == "a"]
    assert pending and pending[0].status == "pending_review"
    assert any(i.reason == "mixed_direct_indirect" for i in r.review)


def test_circular_holdings_terminate_and_are_flagged():
    f = facts("t", [company("t"), company("x"), company("y"), person("a")],
              [("x", "t", 100), ("y", "x", 60), ("x", "y", 60), ("a", "y", 40)])
    r = analyse(f)
    assert any(i.reason == "circular" for i in r.review)
