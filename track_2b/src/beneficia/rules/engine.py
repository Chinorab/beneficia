"""Rules engine: from extracted facts to beneficial owner findings and review items.

Direct control: TJPV art. 1. Indirect control: TJPV art. 2 (control of intermediates, never the product
of percentages). Default manager: TJPG art. 4 para. 2. Bands and type: TJPV art. 12 and 13.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Optional

from beneficia.model import CaseFacts, Finding, LineRef, MissingDocument, ReviewItem
from beneficia.rules import articles as A
from beneficia.rules.bands import QUARTER, HALF, band, control_type
from beneficia.rules.fallback import most_senior
from beneficia.rules.graph import BASES, OwnershipGraph


@dataclass
class AnalysisResult:
    findings: list[Finding] = field(default_factory=list)
    review: list[ReviewItem] = field(default_factory=list)
    missing: list[MissingDocument] = field(default_factory=list)

    def add_review(self, item: ReviewItem) -> None:
        key = (item.reason, tuple(sorted(item.parties)))
        for existing in self.review:
            if (existing.reason, tuple(sorted(existing.parties))) == key:
                for r in item.refs:
                    if r not in existing.refs:
                        existing.refs.append(r)
                return
        self.review.append(item)

    def add_missing(self, item: MissingDocument) -> None:
        if all((m.what, m.about) != (item.what, item.about) for m in self.missing):
            self.missing.append(item)


def controlled_closure(g: OwnershipGraph, person: str, basis: str, target: str) -> set[str]:
    """Legal entities the person controls with more than 50 %, directly or through controlled entities."""
    closure: set[str] = set()
    changed = True
    while changed:
        changed = False
        for x in sorted(g.companies()):
            if x == target or x in closure or not g.is_entity(x):
                continue
            stake = g.share(person, x, basis) + sum((g.share(e, x, basis) for e in closure), Fraction(0))
            if stake > HALF:
                closure.add(x)
                changed = True
    return closure


def _path(g: OwnershipGraph, person: str, end: str, closure: set[str], basis: str) -> list[str]:
    prev: dict[str, Optional[str]] = {person: None}
    queue = deque([person])
    while queue:
        u = queue.popleft()
        if u == end:
            break
        for v in sorted(closure):
            if v not in prev and g.share(u, v, basis) > 0:
                prev[v] = u
                queue.append(v)
    if end not in prev:
        return [person, end]
    path, node = [], end
    while node is not None:
        path.append(node)
        node = prev[node]
    return list(reversed(path))


def chain_refs(g: OwnershipGraph, chain: list[str]) -> list[LineRef]:
    refs: list[LineRef] = []
    for u, v in zip(chain, chain[1:]):
        refs.extend(g.edge_refs.get((u, v), []))
        party = g.parties.get(v)
        if party is not None and party.total_ref is not None:
            refs.append(party.total_ref)
    seen, out = set(), []
    for r in refs:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def person_stake(g: OwnershipGraph, person: str, target: str, basis: str) -> tuple[Fraction, Fraction, dict]:
    closure = controlled_closure(g, person, basis, target)
    direct = g.share(person, target, basis)
    via = {e: g.share(e, target, basis) for e in sorted(closure) if g.share(e, target, basis) > 0}
    return direct, sum(via.values(), Fraction(0)), {"closure": closure, "via": via}


_RANK = {"direct": 3, "indirect": 2, "mixed": 1}


def _qualify(g: OwnershipGraph, person: str, target: str, result: AnalysisResult) -> Optional[Finding]:
    best = None  # (rank, stake, basis_name, kind, detail)
    for basis in BASES:
        direct, via_total, detail = person_stake(g, person, target, basis)
        if direct >= QUARTER:
            cand = ("direct", direct)
        elif via_total >= QUARTER:
            cand = ("indirect", via_total)
        elif direct + via_total >= QUARTER:
            cand = ("mixed", direct + via_total)
        else:
            continue
        key = (_RANK[cand[0]], cand[1])
        if best is None or key > (best[0], best[1]):
            best = (_RANK[cand[0]], cand[1], basis, cand[0], detail)
    if best is None:
        return None

    _, stake, basis, kind, detail = best
    if kind == "direct":
        chain = [person, target]
        arts = [A.TJPG_4_1, A.TJPV_1, A.TJPV_12, A.TJPV_13]
    else:
        via = detail["via"]
        main = max(via, key=lambda e: via[e]) if via else target
        chain = (_path(g, person, main, detail["closure"], basis) + [target]) if via else [person, target]
        arts = [A.TJPG_4_1, A.TJPV_2, A.TJPV_12, A.TJPV_13, A.TJPV_13_3]

    refs = chain_refs(g, chain)
    if kind != "direct":
        for e in detail["via"]:
            refs += [r for r in chain_refs(g, _path(g, person, e, detail["closure"], basis) + [target])
                     if r not in refs]

    status = "settled"
    intermediaries = len(chain) - 2
    edges = list(zip(chain, chain[1:]))
    fiduciary = [e for e in edges if e in g.fiduciary_edges]
    chain_info = intermediaries >= 2 or bool(fiduciary)
    if chain_info:
        arts.append(A.TJPV_15)

    if kind == "mixed":
        status = "pending_review"
        result.add_review(ReviewItem("mixed_direct_indirect", A.TJPV_2, [person], list(refs),
                                     {"share": str(stake)}))
    if fiduciary:
        status = "pending_review"
        nominees = [n for e in fiduciary for n in g.fiduciary_edges[e]]
        result.add_review(ReviewItem("fiduciary", A.TJPV_3_2_E, [person, *nominees], list(refs)))
    shaky = [c for c in chain[1:] if c in g.facts.inconsistent]
    if shaky:
        status = "pending_review"
        result.add_review(ReviewItem("inconsistent_figures", A.TJPV_13, shaky, list(refs)))
    unstated = [c for c in chain[1:] if c in g.total_from_register_sum]
    if unstated:
        status = "pending_review"
        result.add_review(ReviewItem("total_not_stated", A.TJPV_13, unstated, list(refs)))

    finding_basis = "direct" if kind == "direct" else "indirect"
    return Finding(person=person, basis=finding_basis,
                   control_type=control_type(finding_basis), band=band(stake),
                   chain=chain, chain_info_required=chain_info, articles=arts, refs=refs,
                   status=status, share=stake)


def analyse(facts: CaseFacts) -> AnalysisResult:
    from beneficia.rules import missing as missing_rules
    from beneficia.rules import review as review_rules

    g = OwnershipGraph(facts)
    result = AnalysisResult()
    target = facts.target

    for cyc in g.cycles():
        refs = [r for u, v in zip(cyc, cyc[1:] + cyc[:1]) for r in g.edge_refs.get((u, v), [])]
        result.add_review(ReviewItem("circular", A.TJPV_2, sorted(cyc), refs))

    for (principal, company), nominees in sorted(g.fiduciary_edges.items()):
        result.add_review(ReviewItem("fiduciary", A.TJPV_3_2_E, [principal, *nominees],
                                     list(g.edge_refs.get((principal, company), [])), {"company": company}))

    for pid in sorted(p for p in facts.parties if g.is_person(p)):
        finding = _qualify(g, pid, target, result)
        if finding is not None:
            result.findings.append(finding)

    review_rules.apply_agreements(g, facts, result)
    review_rules.check_holders(g, facts, result)

    if not result.findings:
        role, how = most_senior(facts.board, target)
        if role is not None:
            refs = [role.ref] if role.ref else []
            result.findings.append(Finding(
                person=role.person, basis="default_manager", control_type=control_type("default_manager"),
                band=None, chain=[role.person, target], chain_info_required=False,
                articles=[A.TJPG_4_2], refs=refs, status="pending_review"))
            result.add_review(ReviewItem("default_manager", A.TJPG_4_2, [role.person], list(refs)))
        else:
            result.add_review(ReviewItem("default_manager_unclear", A.TJPG_4_2, [],
                                         [b.ref for b in facts.board if b.ref]))
            result.add_missing(MissingDocument("board_extract", target, "default_manager_unclear"))

    review_rules.check_low_confidence(facts, result)
    missing_rules.identification(facts, result)
    result.findings.sort(key=lambda f: (f.status != "settled", -(f.share or 0), f.person))
    return result
