# CI & branch protections

Every PR targeting `main`, every push to `main`, and manual runs execute the `CI` workflow:

- **lint-and-format** — Ruff import/style checks and formatter check.
- **tests-py3.11 / tests-py3.13** — complete `unittest` suite, branch coverage (minimum 80%), and CLI end-to-end test.
- **package-smoke** — build and install a wheel in a clean virtual environment, run the installed CLI, then upload the wheel as an ephemeral build artifact.
- **quality-gate** — a single stable required status that fails unless all prior jobs succeed.

The first release does not deploy to any infrastructure. The GitHub Actions artifact is a
*build artifact*, not a published release. CD/deployment will only be added after a deployment
target and its approval/rollback policy are documented.

## Local validation

Python 3.11+ is required. On Debian use `python3` rather than assuming a `python` command:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e . -r requirements-dev.txt
ruff check .
ruff format --check .
coverage run --branch --source=opencareerops -m unittest discover -s tests -v
coverage report --show-missing --fail-under=80
python -m pip wheel . --no-deps --wheel-dir dist
```

To repair format/import issues *before committing*, run `ruff check --fix .` and
`ruff format .` followed by the verification commands again.

## GitHub repository settings (maintainer action)

In **Settings → Rules → Rulesets**, create an active **branch** ruleset named `protect-main`:

1. Target default branch `main`.
2. Require a pull request before merging. For a solo-maintained repository, do not require approval from another reviewer yet.
3. Require status checks to pass, and select `quality-gate` **after a PR has produced it**. Prefer GitHub Actions as the expected source, and consider requiring the branch to be up to date.
4. Block force pushes and deletions. Do not add a bypass unless operationally necessary.

Do not configure path filters or skip the `quality-gate` job: a skipped required check can
block merges or accidentally hide unvalidated changes.

## Security

- `permissions: contents: read`; no write access, secrets, OIDC permissions, self-hosted runners, or deployment credentials needed.
- `pull_request` rather than `pull_request_target` avoids using trusted-token workflows with untrusted PR code.
- Test records are fictional; never upload real Notion tokens or private career records.
- Dependabot checks GitHub Actions and Python dependencies weekly.
