"""CLI: python -m megapower10 quotes.jsonl --lead-minutes 60 --min-odds 10 --max-odds 15"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .core import load_jsonl, validate_quotes, decision_snapshot, discovery_report, evaluate


def main() -> int:
    p = argparse.ArgumentParser(description="MEGAPOWER 10+ — audit et étude des cotes")
    p.add_argument("input", help="fichier JSONL canonique")
    p.add_argument("--lead-minutes", type=int, default=60)
    p.add_argument("--tolerance-minutes", type=int, default=20)
    p.add_argument("--min-odds", type=float, default=10.0)
    p.add_argument("--max-odds", type=float, default=15.0)
    p.add_argument("--min-support", type=int, default=30)
    p.add_argument("--output", default="-", help="JSON de sortie (défaut: stdout)")
    args = p.parse_args()

    raw = load_jsonl(args.input)
    checked = validate_quotes(raw)
    snap = decision_snapshot(checked["usable"], lead_minutes=args.lead_minutes,
                             tolerance_minutes=args.tolerance_minutes)
    report = {
        "engine": "MEGAPOWER 10+",
        "input": str(args.input),
        "validation": {"input": checked["input"], "usable": len(checked["usable"]),
                       "excluded": checked["excluded"], "errors": checked["errors"]},
        "snapshot": {"groups": snap["groups"], "selected": snap["selected"],
                     "missing_snapshot": snap["missing_snapshot"], "excluded": snap["excluded"],
                     "decision_rule": snap["decision_rule"]},
        "selected_price_evaluation": evaluate(snap["quotes"], min_odds=args.min_odds, max_odds=args.max_odds),
        "discovery": discovery_report(snap["quotes"], min_support=args.min_support),
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    if args.output == "-":
        print(rendered)
    else:
        Path(args.output).write_text(rendered + "\\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
