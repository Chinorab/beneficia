"""Small builders for hand-written, fictitious rule test cases."""
from beneficia.model import BoardRole, CaseFacts, ControlAgreement, Holding, LineRef, Party

_n = [0]


def ref() -> LineRef:
    _n[0] += 1
    return LineRef("D1", 1, _n[0])


def person(pid: str) -> Party:
    return Party(pid, "natural_person", pid.replace("_", " ").title(), [ref()])


def company(pid: str, total: int | None = 100, votes: int | None = None, **kw) -> Party:
    p = Party(pid, "legal_entity", pid.replace("_", " ").title(), [ref()], total_capital=total,
              total_votes=votes, total_ref=ref(), **kw)
    return p


def facts(target: str, parties: list[Party], holdings: list[tuple], agreements=(), board=()) -> CaseFacts:
    """holdings: (holder, company, units[, basis[, held_for]])."""
    hs = []
    for h in holdings:
        holder, comp, units = h[0], h[1], h[2]
        basis = h[3] if len(h) > 3 else "both"
        held_for = h[4] if len(h) > 4 else None
        hs.append(Holding(holder, comp, units, basis, held_for, None, ref()))
    ags = [ControlAgreement(a[0], a[1], a[2], a[3], ref()) for a in agreements]
    brd = [BoardRole(b[0], b[1], b[2], b[3], ref()) for b in board]
    return CaseFacts(target, {p.id: p for p in parties}, hs, ags, brd)
