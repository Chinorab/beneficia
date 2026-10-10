"""Machine-readable result per case (contracts/result.schema.json)."""
from __future__ import annotations

import datetime as dt
from fractions import Fraction
from typing import Optional

from beneficia.model import Document, LineRef

DRAFT_LABEL = "Draft for verification, not filed"


def frac(x: Optional[Fraction]) -> Optional[dict]:
    if x is None:
        return None
    return {"num": x.numerator, "den": x.denominator, "percent": round(float(x) * 100, 2)}


def build(case_id: str, model: str, target_id: str, docs: list[Document], facts, analysis, dropped: list[dict],
          accepted: dict, timings: dict) -> dict:
    from beneficia.rules.graph import OwnershipGraph

    g = OwnershipGraph(facts) if facts is not None else None
    used: set[LineRef] = set()

    def refs(rs) -> list[str]:
        out = []
        for r in rs:
            if r is not None:
                used.add(r)
                out.append(str(r))
        return out

    parties = []
    for p in (facts.parties.values() if facts else []):
        parties.append({
            "id": p.id, "kind": p.kind, "name": p.name, "refs": refs(p.refs),
            "fields": {k: {"value": f.value, "ref": refs([f.ref])[0]} for k, f in p.fields.items()},
            "total_capital": p.total_capital, "total_votes": p.total_votes,
            "total_ref": refs([p.total_ref])[0] if p.total_ref else None,
            "special_kind": p.special_kind,
        })
    holdings = []
    for h in (facts.holdings if facts else []):
        owner = h.held_for or h.holder
        holdings.append({
            "holder": h.holder, "company": h.company, "units_held": h.units_held, "basis": h.basis,
            "held_for": h.held_for, "ref": refs([h.ref])[0] if h.ref else None,
            "capital_share": frac(g.share(owner, h.company, "capital")) if g else None,
            "vote_share": frac(g.share(owner, h.company, "votes")) if g else None,
        })
    findings = [{
        "person": f.person, "basis": f.basis, "control_type": f.control_type, "band": f.band,
        "chain": f.chain, "chain_info_required": f.chain_info_required, "articles": f.articles,
        "refs": refs(f.refs), "status": f.status, "share": frac(f.share),
    } for f in (analysis.findings if analysis else [])]
    review = [{"reason": i.reason, "article": i.article, "parties": i.parties, "refs": refs(i.refs),
               "detail": i.detail} for i in (analysis.review if analysis else [])]
    missing = [{"what": m.what, "about": m.about, "reason": m.reason} for m in (analysis.missing if analysis else [])]

    by_id = {d.id: d for d in docs}
    sources = {}
    for r in sorted(used):
        d = by_id.get(r.doc)
        text = d.line(r.page, r.line) if d else None
        if text is not None:
            sources[str(r)] = {"doc": r.doc, "filename": d.filename, "page": r.page, "line": r.line, "text": text}

    return {
        "case_id": case_id,
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "model": model,
        "draft_label": DRAFT_LABEL,
        "target": target_id or None,
        "documents": [{
            "id": d.id, "filename": d.filename, "kind": d.kind, "language": d.language, "readable": d.readable,
            "error": d.error, "pages": len(d.pages),
            "min_ocr_confidence": min((p.ocr_confidence for p in d.pages if p.ocr_confidence is not None),
                                      default=None),
        } for d in docs],
        "parties": parties,
        "holdings": holdings,
        "agreements": [{"kind": a.kind, "controller": a.controller, "controlled": a.controlled,
                        "company": a.company, "ref": refs([a.ref])[0] if a.ref else None}
                       for a in (facts.agreements if facts else [])],
        "board": [{"person": b.person, "company": b.company, "role_raw": b.role_raw, "role": b.role,
                   "ref": refs([b.ref])[0] if b.ref else None} for b in (facts.board if facts else [])],
        "findings": findings,
        "review": review,
        "missing": missing,
        "sources": sources,
        "dropped_items": {"count": len(dropped), "items": dropped, "accepted": dict(accepted)},
        "timings": timings,
    }
