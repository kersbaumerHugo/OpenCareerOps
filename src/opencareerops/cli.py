"""Command-line entry point for career reviews and job-to-profile evidence checks."""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from opencareerops.curation import render_curated_proposal
from opencareerops.domain import ValidationError, parse_date, parse_state
from opencareerops.job_review import render_job_review
from opencareerops.knowledge import inspect_git_project, render_knowledge_proposal
from opencareerops.llm_writer import generate_llm_proposal
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


def _knowledge_propose_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Propose a traceable Obsidian project note from Git"
    )
    parser.add_argument("--repo", type=Path, required=True, help="local clone of a Git repository")
    parser.add_argument(
        "--output", type=Path, help="optional path outside the repository and vault"
    )
    parser.add_argument(
        "--vault", type=Path, help="optional vault path to enforce read-only output"
    )
    parser.add_argument(
        "--curated", action="store_true", help="synthesize a short, reviewable evidence note"
    )
    parser.add_argument(
        "--writer",
        choices=("deterministic", "llm"),
        default="deterministic",
        help="optional LLM drafting; deterministic behavior is the default",
    )
    parser.add_argument(
        "--llm-base-url", help="OpenAI-compatible API base URL (or OPENCAREEROPS_LLM_BASE_URL)"
    )
    parser.add_argument(
        "--llm-model", help="provider model identifier (or OPENCAREEROPS_LLM_MODEL)"
    )
    parser.add_argument(
        "--allow-remote-llm",
        action="store_true",
        help="explicitly authorize sending selected evidence to a remote HTTPS provider",
    )
    args = parser.parse_args(argv)
    try:
        # Resolve output paths before executing any writes.
        if args.output is not None:
            target = args.output.resolve()
            if target.is_relative_to(args.repo.resolve()):
                raise ValidationError("proposal output must be outside the source repository")
            if args.vault is not None and target.is_relative_to(args.vault.resolve()):
                raise ValidationError("proposal output must be outside the read-only vault")
        if args.writer == "deterministic" and (
            args.llm_base_url or args.llm_model or args.allow_remote_llm
        ):
            raise ValidationError("LLM options require --writer llm")
        proposal = inspect_git_project(args.repo)
        if args.writer == "llm":
            base_url = args.llm_base_url or os.environ.get("OPENCAREEROPS_LLM_BASE_URL", "")
            model = args.llm_model or os.environ.get("OPENCAREEROPS_LLM_MODEL", "")
            if not base_url:
                raise ValidationError("supply --llm-base-url or OPENCAREEROPS_LLM_BASE_URL")
            draft = generate_llm_proposal(
                proposal,
                base_url=base_url,
                model=model,
                allow_remote=args.allow_remote_llm,
                api_key=os.environ.get("OPENCAREEROPS_LLM_API_KEY"),
            )
        else:
            draft = (
                render_curated_proposal(proposal)
                if args.curated
                else render_knowledge_proposal(proposal)
            )
        if args.output is None:
            print(draft)
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(draft, encoding="utf-8")
            print(f"Unapproved proposal written to {args.output}")
    except (OSError, ValueError, UnicodeError, TimeoutError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "job-review":
        return _job_review_main(argv[1:])
    if argv and argv[0] == "knowledge-propose":
        return _knowledge_propose_main(argv[1:])

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
