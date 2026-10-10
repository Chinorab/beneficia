"""Command line: analyze one case, or evaluate all cases (used by make eval and the offline test)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from beneficia import config
from beneficia.extract.client import LLMClient, ModelUnavailable


def _write(result: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "result.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="beneficia")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze")
    a.add_argument("case_dir", type=Path)
    a.add_argument("--target")
    a.add_argument("--out", type=Path)
    e = sub.add_parser("eval")
    e.add_argument("cases_dir", type=Path, nargs="?", default=config.CASES_DIR)
    e.add_argument("--out", type=Path, default=config.OUTPUT_DIR)
    e.add_argument("--only", nargs="*")
    args = ap.parse_args(argv)

    client = LLMClient()
    if not client.health():
        print(f"model server not reachable at {client.base_url}", file=sys.stderr)
        return 2
    try:
        if args.cmd == "analyze":
            from beneficia.pipeline import analyse_case
            result = analyse_case(args.case_dir, client, args.target, progress=lambda s: print(s, flush=True))
            path = _write(result, args.out or (config.OUTPUT_DIR / args.case_dir.name))
            print(f"written {path}")
            return 0
        from beneficia.evaluate import run_eval
        summary = run_eval(args.cases_dir, args.out, args.only)
        print(json.dumps(summary["totals"], indent=1))
        return 0
    except ModelUnavailable as exc:
        print(f"model error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
