# Vault Reader v0 — Obsidian as an optional Git-backed source

## Why

The user registers accomplishments once in their own Markdown notes. `job-review` reads these
files directly, instead of requiring a task backlog or a manually maintained JSON profile.
The existing JSON weekly review and `job-review --profile ...` remain available.

## Local demo

Requires Python 3.13+ and `pip install -e .` (including the PyYAML dependency).

```bash
python -m opencareerops job-review \
  --job examples/fictional_job.txt \
  --vault examples/fictional_vault \
  --output output/vault_job_review.md
cat output/vault_job_review.md
```

For a private personal vault:

```bash
python -m opencareerops job-review \
  --job ~/private/vacancy.txt \
  --vault ~/projects/personal-vault \
  --output output/private_job_review.md
```

The `--profile` flag is optional in vault mode and may be combined with `--vault`.

## Conventions (not mandatory schemas)

- Recognized **top-level** folders: `Career/`, `Projects/`, `Evidence/`, `Learning/`.
- Optional Obsidian YAML frontmatter (`type`, `status`, `tags`, etc.) is parsed using `safe_load`,
  but metadata **never counts as skill evidence**.
- To exclude a note explicitly, add `career_evidence: false` to its frontmatter.
- Normal Markdown body sentences containing known technology terms can be surfaced with
  source file, original line number and a short excerpt. This is textual matching only.
- Headers, fenced code, task checkboxes, sections such as `Next steps` and `Roadmap`,
  negations and explicit plans are filtered heuristically. This cannot fully determine intent.
- A line from a note does not prove production experience, proficiency, skill level or recency.
- The engine is **read-only**. It will not convert notes into tasks, modify Git state, or submit
  applications. Reports are ignored by the public repository only when kept under `output/`.

## Privacy and reproducibility

Maintain the personal vault in a **different private repository**. Never place personal data
under `examples/` or in the public OpenCareerOps engine repo. Keep job descriptions and
reports private, and avoid credentials or excessively sensitive notes in any Git history.
`00-Inbox/`, hidden files and symlinks are not scanned. Readable Markdown is limited to
1 MiB per note / 500 notes per command to bound untrusted inputs.

Use `git diff` and pull/review before applying any future agent-generated edits. No automatic
pushes from the CareerOps engine are needed for this slice.
