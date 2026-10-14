# OpenCareerOps

OpenCareerOps is an open platform for managing career development with engineering principles, automation and explainable recommendations. It connects goals, learning, projects, evidence, applications and personal branding into an improving career system.

## Status: v0.2 — GitOps career state

The Python engine validates structured JSON, ranks actionable tasks deterministically and generates an explainable Markdown report. It needs no LLM or database.

Under [ADR-0002](adr/ADR-002.md), Git is the operational source of truth. **Real career state belongs in a separate, private `career-state` repository**; this public repository contains the engine and fictional fixtures only. Notion is not part of the operational pipeline.

```text
Private Git state/current.json → validation → priorities → private report artifact
Public OpenCareerOps engine  → tests/CI     ↗
```

For the private repository bootstrap, review rules and scheduled workflow, follow the [GitOps guide](docs/development/gitops.md). Do not automatically import older Notion records without reviewing their current accuracy.

### Run the working slice

Requires Python 3.13+; no runtime dependencies.

```bash
PYTHONPATH=src python -m opencareerops \
  --input examples/fictional_career_state.json \
  --output output/weekly_report.md \
  --today 2026-10-14
cat output/weekly_report.md
```

Omit `--today` to use the machine's current date, or `--output` to use `output/weekly_report.md`. To install as a CLI, use `python -m pip install -e .` and then run `opencareerops --help`.

### Test

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

### JSON input contract

`schema_version` must be `1`, `focus` a non-empty string, and `actions` an array. Each action has a unique `id`, `title`, `status` (`todo`, `in_progress`, `blocked`, `done`), integer `impact`, `urgency`, `effort` ratings from 1 to 5, and optional `category` and `due_date` (`YYYY-MM-DD` or `null`). Invalid input fails before a report is written.

Only `todo` and `in_progress` actions are ranked. The formula is `3 × impact + 2 × urgency − effort`, with `+4` if overdue, `+2` if due within seven days (inclusive), and `+1` if in progress. Ties break by earliest due date and then action ID. Every score has an explanation; the report is **advisory**, never an automated decision. "Completed" shows completed actions in the current snapshot, not a historical weekly delta (historical weekly deltas require explicit snapshots/events; Git commits provide edit history).

Never commit real career records or tokens here. Store real operational records only in a private `career-state` repository, keep public test fixtures fictional, and keep generated reports in `output/` (gitignored).

## Product documentation

- [Product vision](docs/product/vision.md)
- [MVP PRD](docs/product/prd.md)
- [Roadmap](docs/product/roadmap.md)
- [Philosophy](docs/philosophy.md)
- [Manifesto](docs/manifesto.md)
- [ADR-0002: Git source of truth](adr/ADR-002.md)
- [GitOps setup and privacy guide](docs/development/gitops.md)
- [Superseded ADR-0001: Notion](adr/ADR-001.md)

## Principles

Career as Code, human-in-the-loop decisions, single source of truth, explainability, evidence over claims, and build in public.

MIT licensed.

### Continuous integration

The [CI workflow](.github/workflows/ci.yml) checks lint/formatting, Python 3.13 tests
and coverage, plus a built-wheel smoke test on each PR and push to `main`.
See [CI and branch protection setup](docs/development/ci.md) for local commands and the
required manual GitHub repository ruleset. There is no production deployment yet.
