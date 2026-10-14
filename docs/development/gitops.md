# GitOps career state (v0.2)

OpenCareerOps is the public engine; the private `career-state` repository is the operational Git source of truth. The starter repository is distributed separately and must **remain private**. Real career records, reports and evidence do not belong in the public engine repository.

## Bootstrap

1. Extract the `opencareerops-career-state-starter.zip` into `~/projects/career-state` on your development machine.
2. Review `state/current.json`. It contains a valid **empty** initial state; populate it with current, verified actions (not stale Notion data). Never add credentials.
3. From that folder, run `git init -b main`, `git add .`, `git commit -m "chore: initialize private career state"` and `gh repo create kersbaumerHugo/career-state --private --source=. --remote=origin --push`. Authenticate `gh` if required.
4. Verify that GitHub shows **Private**, and activate a `main` ruleset requiring PRs and the `validate-and-report` check (where supported).
5. Edit state through a feature branch and PR. Git commit history is the audit log; there is no separate editable history table.

## Local report

With both repositories cloned under `~/projects/`:

```bash
cd ~/projects/career-state
PYTHONPATH=../OpenCareerOps/src python3 -m opencareerops \
  --input state/current.json --output output/weekly_report.md
```

The output is ignored locally. `state/current.json` uses the same schema v1 documented in the public README: unique action IDs, `status`, and 1–5 `impact`, `urgency`, `effort`. Ratings reflect a human evaluation; do not silently map `P0`/`P1` labels from legacy Notion entries to numerical scores. Avoid invented tasks or stale deadlines.

## Private GitHub Actions

The private starter has one read-only workflow. On PRs and pushes to `main`, it runs the pinned public engine against `state/current.json`. On manual dispatch and on Mondays at 12:00 UTC (09:00 BRT), it also uploads a short-lived private report artifact. Schedule times are approximate in GitHub Actions; the workflow is **not** a deployment or an autonomous career decision process.

The workflow pins the public engine to commit `f766e33495695df644560b9c26e2fcf2b7837fd0`, a previously passing CI revision. After changing the public engine, intentionally advance the pinned SHA in the private workflow only after the new commit has passed its quality gate. This prevents a future public code change from silently modifying private career-state validation. No personal access token is needed to read the public engine repo.

Keep the private repo's `GITHUB_TOKEN` read-only (`contents: read`). On PRs no report is uploaded; scheduled/manual reports are accessible only to authorized repository collaborators, subject to GitHub repository permissions. Artifacts are not a privacy vault. Do not make them public, and do not include private data in workflow logs.

## Scope boundary

v0.2 provides versioning, review, input validation and scheduled report generation. It **does not** automatically synchronize Gmail, Notion, job boards, GitHub Issues, or personal records. Cross-source sync, AI suggestions and autonomous writes require separate decisions and explicit approval.
