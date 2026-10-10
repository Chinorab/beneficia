"""Export the evaluation set in the three parts the Hack Apertus dataset template asks for.

  evaluation.jsonl  one test case per line: documents as numbered text, target company, expected answer
  responses.jsonl   the model's raw extraction outputs and the final result for each case
  metadata.jsonl    per-instance information, including the licence

Usage: python export_hf_dataset.py <eval_output_dir> <out_dir>
All cases are fictitious (invented companies and persons), licence CC BY 4.0.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(SRC))

from beneficia.ingest.case import load_case  # noqa: E402

CASES = Path(__file__).resolve().parents[1] / "cases"


def main(eval_dir: str, out_dir: str) -> None:
    eval_path, out = Path(eval_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary = json.loads((eval_path / "summary.json").read_text(encoding="utf-8"))
    scores = {r["case"]: r for r in summary["cases"]}
    with (out / "evaluation.jsonl").open("w", encoding="utf-8") as ev, \
         (out / "responses.jsonl").open("w", encoding="utf-8") as rs, \
         (out / "metadata.jsonl").open("w", encoding="utf-8") as md:
        for case_dir in sorted(p for p in CASES.iterdir() if (p / "expected.json").exists()):
            expected = json.loads((case_dir / "expected.json").read_text(encoding="utf-8"))
            case = load_case(case_dir)
            docs = [{"id": d.id, "filename": d.filename, "kind": d.kind, "language": d.language,
                     "pages": [{"page": p.number, "lines": p.lines} for p in d.pages]} for d in case.documents]
            ev.write(json.dumps({"case_id": case_dir.name, "target": expected["target"], "documents": docs,
                                 "expected": {k: expected[k] for k in ("beneficial_owners", "review_reasons",
                                                                      "holdings") if k in expected}},
                                ensure_ascii=False) + "\n")
            result_file = eval_path / case_dir.name / "result.json"
            if result_file.exists():
                result = json.loads(result_file.read_text(encoding="utf-8"))
                rs.write(json.dumps({
                    "case_id": case_dir.name, "model": result["model"],
                    "raw_extraction_outputs": result.get("model_responses", []),
                    "findings": result["findings"], "review": result["review"], "missing": result["missing"],
                    "holdings": result["holdings"], "dropped_items": result["dropped_items"]["count"],
                    "seconds": result["timings"]["total_s"], "score": scores.get(case_dir.name),
                }, ensure_ascii=False) + "\n")
            md.write(json.dumps({
                "case_id": case_dir.name, "language": expected.get("language"), "fictitious": True,
                "licence": expected.get("licence", "CC-BY-4.0"), "source": "synthetic, written for this project",
                "personal_data": "none (all names invented)", "notes": expected.get("notes", ""),
                "files": [d.filename for d in case.documents],
            }, ensure_ascii=False) + "\n")
    print(f"written {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
