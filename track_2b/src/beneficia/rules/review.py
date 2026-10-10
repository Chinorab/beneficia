"""Cases the text does not settle: control by other means, concert, special or undocumented holders,
low recognition quality. Nothing here produces a settled finding (constitution principle IV)."""
from __future__ import annotations

from fractions import Fraction
from typing import TYPE_CHECKING

from beneficia.model import CaseFacts, Finding, MissingDocument, ReviewItem
from beneficia.rules import articles as A
from beneficia.rules.bands import QUARTER, band, control_type

if TYPE_CHECKING:
    from beneficia.rules.engine import AnalysisResult
    from beneficia.rules.graph import OwnershipGraph


def _vote_stake(g: "OwnershipGraph", pid: str, target: str) -> Fraction:
    from beneficia.rules.engine import person_stake
    direct, via, _ = person_stake(g, pid, target, "votes")
    return direct + via


def apply_agreements(g: "OwnershipGraph", facts: CaseFacts, result: "AnalysisResult") -> None:
    target = facts.target
    found = {f.person for f in result.findings}
    for ag in facts.agreements:
        company = ag.company or target
        refs = [ag.ref] if ag.ref else []
        parties = [p for p in (ag.controller, ag.controlled) if p]
        if ag.kind == "fiduciary":
            result.add_review(ReviewItem("fiduciary", A.TJPV_3_2_E, parties, refs))
            continue
        if ag.kind == "voting":
            result.add_review(ReviewItem("concert", A.TJPV_4, parties, refs))
            if company != target or not g.is_person(ag.controller) or ag.controller in found:
                continue
            combined = _vote_stake(g, ag.controller, target) + _vote_stake(g, ag.controlled, target)
            if combined >= QUARTER:
                result.findings.append(Finding(
                    person=ag.controller, basis="other_means",
                    control_type=control_type("other_means", concert=True), band=band(combined),
                    chain=[ag.controller, target], chain_info_required=False,
                    articles=[A.TJPG_4_1, A.TJPV_3_2_A, A.TJPV_4, A.TJPV_12, A.TJPV_13], refs=refs,
                    status="pending_review", share=combined))
                found.add(ag.controller)
            continue
        # veto, appointment, other: control by other means, never decided automatically
        result.add_review(ReviewItem("other_means", A.TJPV_3, parties, refs, {"kind": ag.kind}))
        if company == target and g.is_person(ag.controller) and ag.controller not in found:
            result.findings.append(Finding(
                person=ag.controller, basis="other_means", control_type=control_type("other_means"),
                band=None, chain=[ag.controller, target], chain_info_required=False,
                articles=[A.TJPG_4_1, A.TJPV_3, A.TJPV_12], refs=refs, status="pending_review"))
            found.add(ag.controller)


def check_holders(g: "OwnershipGraph", facts: CaseFacts, result: "AnalysisResult") -> None:
    """Walk up from the target through entities holding at least 25 % and flag those we cannot see through."""
    seen: set[str] = set()
    frontier = [facts.target]
    while frontier:
        company = frontier.pop()
        for holder in sorted(g.holders_of(company)):
            if holder in seen or not g.is_entity(holder):
                continue
            share = max(g.share(holder, company, b) for b in ("capital", "votes"))
            if share < QUARTER:
                continue
            seen.add(holder)
            party = g.parties[holder]
            refs = list(g.edge_refs.get((holder, company), []))
            if party.special_kind:
                art = A.SPECIAL_KIND_ARTICLE.get(party.special_kind, A.TJPV_3)
                result.add_review(ReviewItem("special_holder", art, [holder], refs,
                                             {"kind": party.special_kind}))
                continue
            if not g.holders_of(holder):
                reason = "foreign_or_undocumented"
                result.add_review(ReviewItem(reason, A.TJPV_2, [holder], refs,
                                             {"foreign": bool(party.foreign)}))
                result.add_missing(MissingDocument("ownership_proof", holder, reason))
                continue
            frontier.append(holder)


def check_low_confidence(facts: CaseFacts, result: "AnalysisResult") -> None:
    low = set(facts.low_confidence_refs)
    if not low:
        return
    for f in result.findings:
        hit = [r for r in f.refs if r in low]
        if hit:
            f.status = "pending_review"
            result.add_review(ReviewItem("low_ocr", A.TJPG_7, [f.person], hit))
