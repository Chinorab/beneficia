from fractions import Fraction

import pytest

from beneficia.rules.bands import band, control_type
from beneficia.rules.engine import analyse
from tests.helpers import company, facts, person


@pytest.mark.parametrize("share,expected", [
    (Fraction(1, 4), "25_50"), (Fraction(1, 2), "25_50"), (Fraction(5001, 10000), "50_75"),
    (Fraction(3, 4), "50_75"), (Fraction(7501, 10000), "75_100"), (Fraction(1), "75_100"),
    (Fraction(2499, 10000), None),
])
def test_band_limits(share, expected):
    assert band(share) == expected


def test_control_type_direct_holding_alone():
    assert control_type("direct") == {"alone_or_concert": "alone", "direct_or_indirect": "direct",
                                      "holding_or_other": "holding"}


def test_direct_finding_has_band_and_type():
    f = facts("t", [company("t", 1000), person("a"), person("b")], [("a", "t", 520), ("b", "t", 480)])
    s = {x.person: x for x in analyse(f).findings}
    assert s["a"].band == "50_75"
    assert s["a"].control_type["direct_or_indirect"] == "direct"
    assert "TJPV art. 13" in s["a"].articles and "TJPV art. 12" in s["a"].articles
    assert s["b"].band == "25_50"
