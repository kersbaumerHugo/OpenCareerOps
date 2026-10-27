"""Command-line entry point for career reviews and job-to-profile evidence checks."""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from opencareerops.domain import ValidationError, parse_date, parse_state
from opencareerops.job_review import render_job_review
from opencareerops.report import render_weekly_report
from opencareerops.vault import read_vault, render_vault_job_review


def _job_review_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Compare vacancy requirements to profile text")
    parser.add_argument("--job", type=Path, required=True, help="vacancy description (.txt or .md)")
    parser.add_argument("--profile", type=Path, help="optional existing CV/profile (.txt or .md)")
    parser.add_argument(
        "--vault", type=Path, help="local Obsidian vault (read-only; career folders only)"
    )
    parser.add_argument("--output", type=Path, default=Path("output/job_review.md"))
    args = parser.parse_args(argv)
    try:
        job = args.job.read_text(encoding="utf-8")
        if args.profile is None and args.vault is None:
            raise ValidationError("supply --profile and/or --vault")
        profile = args.profile.read_text(encoding="utf-8") if args.profile else None
        if args.vault is not None:
            if args.output.resolve().is_relative_to(args.vault.resolve()):
                raise ValidationError("output must be outside the read-only vault")
            notes = read_vault(args.vault)
            report = render_vault_job_review(
                job,
                notes,
                args.job.name,
                profile=profile,
                profile_name=args.profile.name if args.profile else None,
            )
        else:
            assert profile is not None  # validated above
            assert args.profile is not None
            report = render_job_review(job, profile, args.job.name, args.profile.name)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"Job review written to {args.output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "job-review":
        return _job_review_main(argv[1:])

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
