# Evidence Curation v0 — compact, source-backed Obsidian draft

Use the existing `knowledge-propose` CLI with the opt-in `--curated` flag:

```bash
cd ~/projects/OpenCareerOps
python -m opencareerops knowledge-propose \
  --repo ~/projects/agent-platform-cloud-lab \
  --vault ~/projects/personal-vault \
  --curated \
  --output output/cloud-lab-curated.proposed.md
```

The output is an **unapproved Markdown proposal**, not an automatically verified
professional accomplishment or a CV. It groups up to five observations into
reviewable categories: committed IaC configuration, reported provision/health checks,
reported rollback experiments, versioned CI workflows and Compose configurations.
It cites original repository paths and line numbers pinned to Git HEAD. If available,
it includes a short set of documented limitations and environment descriptions.

**Nothing is automatically written into the Obsidian vault.** The output is refused
inside the source repository and the provided `--vault` directory. `career_evidence`
stays `false` until a person checks their contribution, tests, environment and results.

The source scan is restricted to committed files, with the same path/byte filters
and no source-code execution or network calls as the original bootstrap. The curation
is deterministic, rule based, and intentionally does not infer responsibility,
production deployments, AWS parity, proficiency, financial impact or business impact.
A missing category means **no supporting signal was found**, not that the project lacks
that capability. The limits section is not exhaustive.

The old detailed view remains unchanged and is still the default:

```bash
python -m opencareerops knowledge-propose \
  --repo ~/projects/agent-platform-cloud-lab \
  --output output/cloud-lab-detailed.proposed.md
```

When the curated note is correct and personally attributable, copy it manually into
`Projects/` of your **private** Obsidian vault, edit/review the text and only then set
`career_evidence: true`. The downstream `job-review --vault` reads approved notes.
Do not commit private CVs, credentials, personal data or actual job documents to the
public OpenCareerOps repository.

## Acceptance checks

- Existing default `knowledge-propose` output and `job-review` remain compatible.
- An input with many early observations still retains later release/rollback evidence.
- Every candidate category and limitation has a `path:Lnumber` source reference;
  GitHub references include the scanned commit SHA.
- At most five categories, three references per category and three limitations.
- Empty/unrelated inputs do not produce invented accomplishments.
- The note remains `status: proposed` and `career_evidence: false` until reviewed.
