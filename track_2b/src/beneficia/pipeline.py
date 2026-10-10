"""Case folder -> result dict. Apertus extracts, code decides."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

from beneficia import config
from beneficia.extract.passes import run_passes
from beneficia.extract.resolve import Resolver
from beneficia.ingest.case import load_case
from beneficia.ingest.ocr import LOW_CONFIDENCE
from beneficia.model import MissingDocument, ReviewItem
from beneficia.report import result as result_mod
from beneficia.rules import articles as A
from beneficia.rules.engine import AnalysisResult, analyse
from beneficia.validate import validate


def _all_refs(facts):
    for p in facts.parties.values():
        yield from p.refs
        yield from (f.ref for f in p.fields.values())
        if p.total_ref:
            yield p.total_ref
    for h in facts.holdings:
        yield h.ref
    for a in facts.agreements:
        yield a.ref
    for b in facts.board:
        yield b.ref


def analyse_case(path: Path, client, target: Optional[str] = None,
                 progress: Optional[Callable[[str], None]] = None) -> dict:
    t0 = time.time()
    case = load_case(Path(path))
    if target:
        case.target = target
    t_ingest = time.time() - t0

    resolver = Resolver(case.docs, case.target)
    extra_review: list[ReviewItem] = []
    extra_missing: list[MissingDocument] = []
    per_doc = {}
    model_log: list[dict] = []
    for doc in case.documents:
        if not doc.readable:
            extra_review.append(ReviewItem("unreadable_document", A.TJPG_7, [], [], {"doc": doc.filename,
                                                                                     "error": doc.error}))
            extra_missing.append(MissingDocument("readable_copy", doc.id, doc.error or "unreadable"))
            continue
        t1 = time.time()
        for row in run_passes(doc, client.complete_json, progress, model_log):
            resolver.add(row)
        per_doc[doc.id] = round(time.time() - t1, 1)

    res = resolver.finish()
    facts = res.facts
    low_pages = {(d.id, p.number) for d in case.documents for p in d.pages
                 if p.ocr_confidence is not None and p.ocr_confidence < LOW_CONFIDENCE}
    facts.low_confidence_refs = sorted({r for r in _all_refs(facts) if r and (r.doc, r.page) in low_pages})
    for d in case.documents:
        for p in d.pages:
            if (d.id, p.number) in low_pages:
                extra_missing.append(MissingDocument("readable_copy", d.id, f"low_ocr_page_{p.number}"))

    validation = validate(facts, getattr(res, "totals_seen", {}))
    if facts.target and any(h.company == facts.target for h in facts.holdings):
        analysis = analyse(facts)
    else:
        analysis = AnalysisResult()
        analysis.add_review(ReviewItem("no_share_information", A.TJPV_1, [facts.target] if facts.target else [], []))
        analysis.add_missing(MissingDocument("share_register", facts.target or case.id, "no_share_information"))
    for item in validation + extra_review:
        analysis.add_review(item)
    for m in extra_missing:
        analysis.add_missing(m)

    timings = {"ingest_s": round(t_ingest, 1), "extract_per_doc_s": per_doc,
               "total_s": round(time.time() - t0, 1), "model_calls": len(getattr(client, "calls", [])),
               "model_seconds": round(sum(c["seconds"] for c in getattr(client, "calls", [])), 1)}
    out = result_mod.build(case.id, getattr(client, "model", config.LLM_NAME), facts.target, case.documents,
                           facts, analysis, res.dropped, res.accepted, timings)
    out["model_responses"] = model_log
    return out
