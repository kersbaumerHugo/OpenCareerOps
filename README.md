# OpenCareerOps

OpenCareerOps is an open platform for managing career development with engineering principles, automation and explainable recommendations. It connects goals, learning, projects, evidence, applications and personal branding into an improving career system.

## Status: v0.1 vertical slice

The first working slice validates a **fictional JSON snapshot**, deterministically ranks actionable tasks, and renders a weekly Markdown report. It needs no account, model, API key or database, so it can run in CI and on a developer machine.

**The intended operational source of truth remains Notion** (ADR-0001). A Notion-to-domain adapter is the next integration step; the example file is a test fixture, not a competing source of truth.

```text
v0.1 now:  JSON fixture → validation → explained priorities → Markdown report
next:      Notion API    → same domain contract  → same report generator
```

### Run the working slice

Requires Python 3.11+; no runtime dependencies.

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

Only `todo` and `in_progress` actions are ranked. The formula is `3 × impact + 2 × urgency − effort`, with `+4` if overdue, `+2` if due within seven days (inclusive), and `+1` if in progress. Ties break by earliest due date and then action ID. Every score has an explanation; the report is **advisory**, never an automated decision. "Completed" shows completed actions in the current snapshot, not a historical weekly delta (history comes with the Notion adapter).

Never commit real career records or Notion tokens. Put private snapshots under `private/` (gitignored), keep generated reports in `output/` (gitignored), and use fictional fixtures in the public repo.

## Product documentation

- [Product vision](docs/product/vision.md)
- [MVP PRD](docs/product/prd.md)
- [Roadmap](docs/product/roadmap.md)
- [Philosophy](docs/philosophy.md)
- [Manifesto](docs/manifesto.md)
- [Architecture decision: Notion source of truth](adr/ADR-001.md)

## Principles

Career as Code, human-in-the-loop decisions, single source of truth, explainability, evidence over claims, and build in public.

MIT licensed.

### Continuous integration

The [CI workflow](.github/workflows/ci.yml) checks lint/formatting, Python 3.11/3.13 tests
and coverage, plus a built-wheel smoke test on each PR and push to `main`.
See [CI and branch protection setup](docs/development/ci.md) for local commands and the
required manual GitHub repository ruleset. There is no production deployment yet.
