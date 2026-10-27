# Knowledge Bootstrap v0 — propose an Obsidian project note from Git

No JSON tasks, LLM, database, GitHub token, or network call is required. The process
reads **a local Git checkout**, pinned to the current commit at `HEAD`, including
committed README, `docs/evidence/`, IaC and CI files. It does not read uncommitted
work or run scripts from the source repository.

## First real project: Agent Platform Cloud Lab

```bash
# Only necessary if the project has not yet been cloned:
git clone https://github.com/kersbaumerHugo/agent-platform-cloud-lab.git \
  ~/projects/agent-platform-cloud-lab

cd ~/projects/OpenCareerOps
python -m opencareerops knowledge-propose \
  --repo ~/projects/agent-platform-cloud-lab \
  --vault ~/projects/personal-vault \
  --output output/agent-platform-cloud-lab.proposed.md

# Read before approving
less output/agent-platform-cloud-lab.proposed.md
```

Omit `--output` to inspect a proposed note directly in the terminal without creating
any file. With `--output`, the CLI refuses to write into the source repository or
explicitly selected `--vault` directory. Generated outputs belong outside the vault.

Review source links, author contribution and confirmed outcomes. **In this project,
Floci results are from local emulation, not proof of AWS production parity.**
The parser records textual evidence and configuration, not validated expertise.
It deliberately skips README roadmap/future sections and typical secret lines.

Only after manually reviewing the proposed note, copy it to the private Obsidian vault:

```bash
cp output/agent-platform-cloud-lab.proposed.md \
  ~/projects/personal-vault/Projects/Agent\ Platform\ Cloud\ Lab.md
```

Inside Obsidian, replace the draft language with verified facts and change
`career_evidence: false` to `career_evidence: true` **only if approved**.
The existing `job-review --vault` can then read accepted evidence. If notes include
personal or sensitive details, never publish the vault or workflow report publicly.

## Safeguards and limitations

- Git `HEAD` is the input snapshot. Run `git pull --ff-only` in the source repo if a
  newer committed revision is desired. Changes not committed remain unread.
- Commit-pinned links are shown only for safe GitHub origin URLs.
- No secret scanning is complete: treat the result as private until manually checked.
- Input is restricted to a fixed file allowlist (up to 120 source files, 1 MiB total,
  per-file maximum 256 KiB). Oversized files are skipped; overall excess is an error.
- No automatic source-vault synchronization, task creation, application submission,
  or inference of personal achievements.
