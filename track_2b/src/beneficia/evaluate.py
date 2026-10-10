"""Batch evaluation over fictitious cases with expected.json (contracts/case-folder.md)."""
from __future__ import annotations

import json
import platform
import time
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Optional

from beneficia.extract.client import LLMClient
from beneficia.parties import match_key
from beneficia.pipeline import analyse_case


def _key(name: Optional[str]) -> Optional[str]:
    return match_key(name) if name else None


def _holding_key(holder, company, units, percent, held_for):
    amount = ("u", int(units)) if units else ("p", str(Fraction(str(percent)))) if percent else None
    return (_key(holder), _key(company), amount, _key(held_for))


def score_case(result: dict, expected: dict) -> dict:
    names = {p["id"]: p["name"] for p in result["parties"]}

    pred_h = set()
    for h in result["holdings"]:
        pct = None
        if not h["units_held"] and h["capital_share"]:
            pct = Fraction(h["capital_share"]["num"], h["capital_share"]["den"]) * 100
        pred_h.add(_holding_key(names.get(h["holder"]), names.get(h["company"]), h["units_held"], pct,
                                names.get(h["held_for"]) if h["held_for"] else None))
    exp_h = {_holding_key(x["holder"], x["company"], x.get("units_held"), x.get("percent"), x.get("held_for"))
             for x in expected.get("holdings", [])}
    tp = len(pred_h & exp_h)

    pred_bo = {_key(names.get(f["person"], f["person"])): f for f in result["findings"]}
    exp_bo = {_key(b["name"]): b for b in expected.get("beneficial_owners", [])}
    bo_errors = []
    for k, b in exp_bo.items():
        f = pred_bo.get(k)
        if f is None:
            bo_errors.append(f"missing {b['name']}")
            continue
        if f["basis"] != b["basis"] or f["band"] != b["band"]:
            bo_errors.append(f"{b['name']}: got {f['basis']}/{f['band']}, expected {b['basis']}/{b['band']}")
        if b["status"] != "any" and f["status"] != b["status"]:
            bo_errors.append(f"{b['name']}: status {f['status']}, expected {b['status']}")
        if b.get("chain_info_required") and not f["chain_info_required"]:
            bo_errors.append(f"{b['name']}: chain information not flagged")
    extra = [k for k in pred_bo if k not in exp_bo]
    for k in extra:
        bo_errors.append(f"unexpected {names.get(pred_bo[k]['person'], k)} ({pred_bo[k]['status']})")
    silent = [k for k in extra if pred_bo[k]["status"] == "settled"]
    silent += [k for k, b in exp_bo.items() if k in pred_bo and pred_bo[k]["status"] == "settled"
               and (pred_bo[k]["basis"] != b["basis"] or pred_bo[k]["band"] != b["band"])]

    got_reasons = {r["reason"] for r in result["review"]}
    missing_reasons = [r for r in expected.get("review_reasons", []) if r not in got_reasons]

    refs = set()
    for key in ("holdings", "agreements", "board"):
        refs |= {x["ref"] for x in result[key] if x.get("ref")}
    for f in result["findings"] + result["review"]:
        refs |= set(f["refs"])
    valid = sum(1 for r in refs if r in result["sources"])

    return {
        "holdings": {"tp": tp, "predicted": len(pred_h), "expected": len(exp_h),
                     "false_positives": sorted(map(str, pred_h - exp_h)), "missed": sorted(map(str, exp_h - pred_h))},
        "owners_correct": not bo_errors,
        "owner_errors": bo_errors,
        "review_recall_complete": not missing_reasons,
        "missing_review_reasons": missing_reasons,
        "silent_errors": len(silent),
        "citations": {"total": len(refs), "valid": valid},
        "case_correct": not bo_errors and not missing_reasons,
    }


def _ratio(a: int, b: int) -> Optional[float]:
    return round(a / b, 3) if b else None


def run_eval(cases_dir: Path, out_dir: Path, only: Optional[list[str]] = None, client=None) -> dict:
    cases_dir, out_dir = Path(cases_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    client = client or LLMClient()
    rows = []
    for case in sorted(p for p in cases_dir.iterdir() if (p / "expected.json").exists()):
        if only and case.name not in only:
            continue
        expected = json.loads((case / "expected.json").read_text(encoding="utf-8"))
        client.calls = []
        t0 = time.time()
        result = analyse_case(case, client, progress=lambda s: print(f"  {case.name} {s}", flush=True))
        seconds = round(time.time() - t0, 1)
        (out_dir / case.name).mkdir(parents=True, exist_ok=True)
        (out_dir / case.name / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                                        encoding="utf-8")
        score = score_case(result, expected)
        score.update({"case": case.name, "language": expected.get("language", "unknown"), "seconds": seconds,
                      "documents": len(result["documents"]), "model_calls": result["timings"]["model_calls"]})
        rows.append(score)
        print(f"{case.name}: correct={score['case_correct']} holdings {score['holdings']['tp']}/"
              f"{score['holdings']['expected']} ({score['holdings']['predicted']} predicted) {seconds}s "
              f"{'; '.join(score['owner_errors'] + score['missing_review_reasons'])}", flush=True)

    by_lang = defaultdict(lambda: {"tp": 0, "predicted": 0, "expected": 0})
    for r in rows:
        for k in ("tp", "predicted", "expected"):
            by_lang[r["language"]][k] += r["holdings"][k]
            by_lang["all"][k] += r["holdings"][k]
    totals = {
        "cases": len(rows),
        "cases_correct": sum(r["case_correct"] for r in rows),
        "owners_correct": sum(r["owners_correct"] for r in rows),
        "review_recall_complete": sum(r["review_recall_complete"] for r in rows),
        "silent_errors": sum(r["silent_errors"] for r in rows),
        "citation_validity": _ratio(sum(r["citations"]["valid"] for r in rows),
                                    sum(r["citations"]["total"] for r in rows)),
        "holdings": {lang: {"precision": _ratio(v["tp"], v["predicted"]), "recall": _ratio(v["tp"], v["expected"]),
                            **v} for lang, v in sorted(by_lang.items())},
        "seconds_per_case_mean": round(sum(r["seconds"] for r in rows) / len(rows), 1) if rows else None,
        "seconds_per_case_max": max((r["seconds"] for r in rows), default=None),
    }
    summary = {"model": client.model, "machine": {"platform": platform.platform(), "processor": platform.processor()},
               "totals": totals, "cases": rows}
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary
