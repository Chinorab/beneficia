"""Extent of the holding (TJPV art. 13) and type of control (TJPV art. 12)."""
from __future__ import annotations

from fractions import Fraction
from typing import Optional

QUARTER, HALF, THREE_QUARTERS = Fraction(1, 4), Fraction(1, 2), Fraction(3, 4)


def band(share: Fraction) -> Optional[str]:
    """TJPV art. 13 para. 1: at least 25 and at most 50; over 50 and at most 75; over 75."""
    if share < QUARTER:
        return None
    if share <= HALF:
        return "25_50"
    if share <= THREE_QUARTERS:
        return "50_75"
    return "75_100"


def control_type(basis: str, concert: bool = False, indirect: Optional[bool] = None) -> dict:
    """TJPV art. 12: alone or in concert, direct or indirect, by holding or by other means."""
    is_indirect = (basis == "indirect") if indirect is None else indirect
    return {
        "alone_or_concert": "concert" if concert else "alone",
        "direct_or_indirect": "indirect" if is_indirect else "direct",
        "holding_or_other": "holding" if basis in ("direct", "indirect") else "other",
    }
