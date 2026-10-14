"""Command-line entry point for generating a local weekly review."""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from opencareerops.domain import ValidationError, parse_date, parse_state
from opencareerops.report import render_weekly_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate an explainable weekly career review")
    parser.add_argument("--input", type=Path, required=True, help="career state JSON snapshot")
    parser.add_argument("--output", type=Path, default=Path("output/weekly_report.md"))
    parser.add_argument(
        "--today", default=date.today().isoformat(), help="reference date (YYYY-MM-DD)"
    )
    parser.add_argument("--limit", type=int, default=5, help="maximum number of top priorities")
    args = parser.parse_args(argv)

    try:
        today = parse_date(args.today, "today")
        if args.limit < 1:
            raise ValidationError("limit must be at least 1")
        state = parse_state(json.loads(args.input.read_text(encoding="utf-8")))
        report = render_weekly_report(state, today, args.limit)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(f"Report written to {args.output}")
    return 0
