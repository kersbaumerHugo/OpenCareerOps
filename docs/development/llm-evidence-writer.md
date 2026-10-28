# LLM Evidence Writer v0

The existing `knowledge-propose` command can now optionally use a text-generation model to
write a **proposed**, source-linked Markdown summary from curated Git evidence. There is
no model requirement for the default deterministic flows.

## Local OpenAI-compatible endpoint

Start a local Chat Completions-compatible API separately (for example, through your existing
model gateway, local runtime or inference server). Its host, port and **model ID are
provider-specific**; the following values are illustrative, not a claim that a service is
running on the machine:

```bash
cd ~/projects/OpenCareerOps
python -m opencareerops knowledge-propose \
  --repo ~/projects/agent-platform-cloud-lab \
  --vault ~/projects/personal-vault \
  --writer llm \
  --llm-base-url http://127.0.0.1:8000/v1 \
  --llm-model YOUR_LOCAL_MODEL_ID \
  --output output/cloud-lab-llm.proposed.md
```

`--writer llm` uses the curated evidence packet automatically. `--curated` without
`--writer llm` remains strictly deterministic. No auto-discovery of running servers,
network provider configuration or automatic fallback occurs.

## Remote HTTPS endpoint (explicit opt-in)

```bash
export OPENCAREEROPS_LLM_BASE_URL='https://YOUR_PROVIDER_HOST/v1'
export OPENCAREEROPS_LLM_MODEL='YOUR_MODEL_ID'
# Provide a key by your local secret manager; do not paste it into Git or shell history.
export OPENCAREEROPS_LLM_API_KEY='YOUR_KEY'

python -m opencareerops knowledge-propose \
  --repo ~/projects/agent-platform-cloud-lab \
  --vault ~/projects/personal-vault \
  --writer llm \
  --allow-remote-llm \
  --output output/cloud-lab-llm.proposed.md
```

**Privacy:** remote mode transmits selected repository excerpts and their semantic
categories. Use it only after confirming that the provider may process this material.
Loopback endpoints may use HTTP; remote providers must use HTTPS. Redirects are not
followed. CLI errors omit request/response bodies and authorization material.

## Input/output contract

Only the read-only committed snapshot is scanned. The model sees a bounded JSON
packet containing candidate categories, an evidence-ID/excerpt list, documented
limitations and environment hints. It must respond with JSON shaped like:

```json
{
  "claims": [
    {"text": "O repositório documenta ...", "evidence_ids": ["E001", "E004"]}
  ],
  "limitations": [
    {"text": "O ambiente usa emulação ...", "evidence_ids": ["E007"]}
  ]
}
```

IDs are temporary and valid only for **that** scan. The CLI validates structure,
reference membership and simple conservative wording constraints, and replaces each
ID with a commit-pinned file/line reference. Neither a cited sentence nor a model
response is automatically proof of execution, authorship, seniority or results.

The resulting note always has `status: proposed`, `writer: llm` and
`career_evidence: false`. The app never writes to the private vault; review each
claim, confirm sources and remove unsupported text **before** you choose to copy it
into `Projects/` and approve it. Keep contextual limitations as distinct, non-career
claims. The current Vault Reader uses textual matching, so approval remains a manual
security/trust decision.

If an endpoint returns malformed/unsupported output, the command exits with code 2,
without creating a new report. Use the existing deterministic fallback explicitly:

```bash
python -m opencareerops knowledge-propose \
  --repo ~/projects/agent-platform-cloud-lab \
  --curated \
  --output output/cloud-lab-deterministic.proposed.md
```

## Validation (no model required)

```bash
ruff check .
ruff format --check .
coverage run --branch --source=opencareerops -m unittest discover -s tests -v
coverage report --show-missing --fail-under=80
```

The unit suite mocks model responses; CI must never transmit repository content to
an external API. This pilot supports simple OpenAI-compatible Chat Completions
(`choices[0].message.content` as a JSON string), not provider-specific tool calling,
streaming, JSON Schema dialects or multimodal responses.
