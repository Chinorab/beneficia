"""Turn one or more evaluation summaries into Markdown tables (no number is typed by hand).

Usage: python docs/eval_to_md.py label1=path/to/summary.json [label2=...] > table.md
"""
from __future__ import annotations

import json
import sys


def pct(x):
    return "n/a" if x is None else f"{x * 100:.0f} %"


def main(args: list[str]) -> None:
    runs = []
    for a in args:
        label, path = a.split("=", 1)
        runs.append((label, json.load(open(path, encoding="utf-8"))))

    print("| Metric | " + " | ".join(label for label, _ in runs) + " |")
    print("|---|" + "---|" * len(runs))
    rows = [
        ("Cases", lambda t: str(t["cases"])),
        ("Cases fully correct (owners and review)", lambda t: f"{t['cases_correct']} / {t['cases']}"),
        ("Beneficial owners exactly right", lambda t: f"{t['owners_correct']} / {t['cases']}"),
        ("Expected review reasons all raised", lambda t: f"{t['review_recall_complete']} / {t['cases']}"),
        ("Silent errors (settled and wrong)", lambda t: str(t["silent_errors"])),
        ("Citation validity", lambda t: pct(t["citation_validity"])),
        ("Holdings precision (all)", lambda t: pct(t["holdings"]["all"]["precision"])),
        ("Holdings recall (all)", lambda t: pct(t["holdings"]["all"]["recall"])),
    ]
    for lang in ("de", "fr", "it"):
        rows.append((f"Holdings recall ({lang.upper()})",
                     lambda t, lang=lang: pct(t["holdings"].get(lang, {}).get("recall"))))
    rows += [("Seconds per case, mean", lambda t: str(t["seconds_per_case_mean"])),
             ("Seconds per case, max", lambda t: str(t["seconds_per_case_max"]))]
    for name, f in rows:
        print(f"| {name} | " + " | ".join(f(s["totals"]) for _, s in runs) + " |")

    label, last = runs[-1]
    print(f"\n**Per case ({label})**\n")
    print("| Case | Lang | Docs | Correct | Holdings found | Seconds | Errors |")
    print("|---|---|---|---|---|---|---|")
    for r in last["cases"]:
        errs = "; ".join(r["owner_errors"] + [f"review missing: {x}" for x in r["missing_review_reasons"]]) or ""
        print(f"| {r['case']} | {r['language'].upper()} | {r['documents']} | {'yes' if r['case_correct'] else 'no'} | "
              f"{r['holdings']['tp']}/{r['holdings']['expected']} ({r['holdings']['predicted']} predicted) | "
              f"{r['seconds']} | {errs} |")


if __name__ == "__main__":
    main(sys.argv[1:])
