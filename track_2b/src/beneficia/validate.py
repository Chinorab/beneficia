"""Consistency checks on extracted figures. Problems become review items; the companies concerned are
marked so that no threshold decision relies on them silently (spec FR-008, US2 scenario 4)."""
from __future__ import annotations

from collections import defaultdict

from beneficia.model import CaseFacts, LineRef, ReviewItem
from beneficia.rules import articles as A


def validate(facts: CaseFacts, totals_seen: dict[str, list[tuple[int, str, LineRef]]] | None = None) -> list[ReviewItem]:
    items: list[ReviewItem] = []

    def flag(company: str, refs: list[LineRef], detail: dict) -> None:
        facts.inconsistent.add(company)
        items.append(ReviewItem("inconsistent_figures", A.TJPV_13, [company], refs, detail))

    for company, seen in (totals_seen or {}).items():
        cap_values = {t for t, kind, _ in seen if kind != "votes"}
        if len(cap_values) > 1:
            flag(company, [r for _, _, r in seen], {"check": "conflicting_totals",
                                                    "values": sorted(cap_values)})

    by_company: dict[str, list] = defaultdict(list)
    for h in facts.holdings:
        if h.basis in ("capital", "both"):
            by_company[h.company].append(h)

    for company, hs in by_company.items():
        party = facts.parties.get(company)
        total = party.total_capital if party else None
        refs = [h.ref for h in hs if h.ref] + ([party.total_ref] if party and party.total_ref else [])
        if total is None:
            continue
        over = [h for h in hs if h.units_held > total]
        if over:
            flag(company, refs, {"check": "holding_exceeds_total", "total": total})
            continue
        s = sum(h.units_held for h in hs)
        if s != total:
            flag(company, refs, {"check": "sum_differs_from_total", "sum": s, "total": total})
    return items
