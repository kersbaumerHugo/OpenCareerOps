# Job Review — First working slice

Review a vacancy against an existing CV/profile, without manually registering actions.

```bash
PYTHONPATH=src python -m opencareerops job-review \
  --job examples/fictional_job.txt \
  --profile examples/fictional_profile.md \
  --output output/job_review.md
```

Inputs are **UTF-8 text** (`.txt` or `.md`). Paste a real job description into a private `.txt` file and use an existing text-based CV or professional profile for `--profile`. PDFs require conversion to text outside this command; job links are not yet fetched automatically.

The review lists requirement bullets, recognized technology terms, line-numbered profile mentions, absent mentions, and items requiring human review. It **does not** assert qualifications, produce an ATS score, validate years of experience or soft skills, or generate a CV. Text mentions can be inaccurate, ambiguous, or lack context; verify before using in an application.

The command neither calls external services nor modifies the career-state repository. Keep real CVs/job descriptions out of the public engine Git repo. `output/` is gitignored.

## Definition of Done

- Fictional vacancy and profile generate a Markdown report.
- Existing weekly-review CLI remains backwards compatible.
- Missing/partial/unknown requirements are explicit, not fabricated.
- Automated tests exercise the CLI and failure paths.

## Next vertical slice

Add an optional *approved evidence store* and resume adaptation draft that strictly cites verified accomplishments. No autonomous applications or career-task generation.
