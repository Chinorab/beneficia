"""Ownership graph with exact shares per basis (capital, votes)."""
from __future__ import annotations

from collections import defaultdict
from fractions import Fraction

from beneficia.model import CaseFacts, LineRef

BASES = ("capital", "votes")


class OwnershipGraph:
    def __init__(self, facts: CaseFacts):
        self.facts = facts
        self.parties = facts.parties
        self.units: dict[tuple[str, str, str], int] = defaultdict(int)  # (owner, company, basis)
        self.edge_refs: dict[tuple[str, str], list[LineRef]] = defaultdict(list)
        self.fiduciary_edges: dict[tuple[str, str], list[str]] = {}  # (principal, company) -> nominees
        self.total_from_register_sum: set[str] = set()
        has_vote_lines: set[str] = set()

        for h in facts.holdings:
            owner = h.held_for or h.holder
            key = (owner, h.company)
            if h.held_for:
                self.fiduciary_edges.setdefault(key, []).append(h.holder)
            if h.ref:
                self.edge_refs[key].append(h.ref)
            if h.basis in ("capital", "both"):
                self.units[(owner, h.company, "capital")] += h.units_held
            if h.basis == "votes":
                self.units[(owner, h.company, "votes")] += h.units_held
                has_vote_lines.add(h.company)
        # one unit one vote unless the documents list votes separately
        for (owner, comp, basis), n in list(self.units.items()):
            if basis == "capital" and comp not in has_vote_lines:
                self.units[(owner, comp, "votes")] += n

        self.totals: dict[tuple[str, str], int] = {}
        companies = {c for (_, c, _) in self.units}
        for comp in companies:
            party = self.parties.get(comp)
            for basis in BASES:
                stated = None
                if party is not None:
                    stated = party.total_capital if basis == "capital" else (
                        party.total_votes if party.total_votes is not None
                        else (party.total_capital if comp not in has_vote_lines else None))
                if stated:
                    self.totals[(comp, basis)] = stated
                else:
                    s = sum(n for (o, c, b), n in self.units.items() if c == comp and b == basis)
                    if s:
                        self.totals[(comp, basis)] = s
                        self.total_from_register_sum.add(comp)

    def share(self, owner: str, company: str, basis: str) -> Fraction:
        total = self.totals.get((company, basis))
        n = self.units.get((owner, company, basis), 0)
        if not total or not n:
            return Fraction(0)
        return Fraction(n, total)

    def holders_of(self, company: str) -> set[str]:
        return {o for (o, c, _), n in self.units.items() if c == company and n > 0}

    def companies(self) -> set[str]:
        return {c for (_, c, _) in self.units}

    def is_entity(self, pid: str) -> bool:
        p = self.parties.get(pid)
        return p is not None and p.kind == "legal_entity"

    def is_person(self, pid: str) -> bool:
        p = self.parties.get(pid)
        return p is not None and p.kind == "natural_person"

    def cycles(self) -> list[list[str]]:
        """Cycles among legal entities in the holding graph (holder -> company)."""
        adj: dict[str, set[str]] = defaultdict(set)
        for (o, c, _), n in self.units.items():
            if n and self.is_entity(o):
                adj[o].add(c)
        found, seen_keys = [], set()
        state: dict[str, int] = {}
        stack: list[str] = []

        def visit(u: str) -> None:
            state[u] = 1
            stack.append(u)
            for v in sorted(adj[u]):
                if state.get(v) == 1:
                    cyc = stack[stack.index(v):]
                    key = frozenset(cyc)
                    if key not in seen_keys:
                        seen_keys.add(key)
                        found.append(list(cyc))
                elif state.get(v) is None:
                    visit(v)
            stack.pop()
            state[u] = 2

        for node in sorted(adj):
            if state.get(node) is None:
                visit(node)
        return found
