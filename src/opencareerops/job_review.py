"""Conservative, traceable job-to-profile review without an LLM or task entry."""

import html
import re
from dataclasses import dataclass

# Explicit lexicon. A match is a textual mention, NOT proof of proficiency.
SKILLS: dict[str, tuple[str, ...]] = {
    "Python": (r"\bpython(?:\s*3(?:\.\d+)?)?\b",),
    "AWS": (r"\baws\b", r"\bamazon web services\b"),
    "Azure": (r"\bazure\b",),
    "GCP": (r"\bgcp\b", r"\bgoogle cloud(?: platform)?\b"),
    "Docker": (r"\bdocker\b",),
    "Kubernetes": (r"\bkubernetes\b", r"\bk8s\b", r"\bk3s\b"),
    "Terraform": (r"\bterraform\b",),
    "OpenTofu": (r"\bopentofu\b", r"\bopen[ -]?tofu\b"),
    "Linux": (r"\blinux\b", r"\bdebian\b", r"\bubuntu\b"),
    "Git": (r"\bgit\b",),
    "GitHub Actions": (r"\bgithub actions\b",),
    "CI/CD": (r"\bci\s*/\s*cd\b", r"\bcontinuous integration\b"),
    "Ansible": (r"\bansible\b",),
    "Prometheus": (r"\bprometheus\b",),
    "Grafana": (r"\bgrafana\b",),
    "SQL": (r"\bsql\b",),
    "FastAPI": (r"\bfastapi\b",),
    "RAG": (r"\brag\b", r"\bretrieval.augmented generation\b"),
    "LLMOps": (r"\bllmops\b",),
}

BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
NEGATED = re.compile(
    r"\b(?:não\s+(?:tenho|possuo|conheço|domino|usei|utilizei|trabalhei)|"
    r"sem experiência|quero aprender|estudando|aprendendo|"
    r"no experience|never used|learning)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Finding:
    requirement: str
    skills: tuple[str, ...]
    mentions: tuple[tuple[str, int, str], ...]
    missing: tuple[str, ...]
    status: str


def _markdown(value: str) -> str:
    """Escape untrusted plain text before inserting it in Markdown."""
    escaped = html.escape(value.replace("\r", " ").replace("\n", " "), quote=False)
    for ch in ("\\", "`", "*", "_", "[", "]", "|"):
        escaped = escaped.replace(ch, "\\" + ch)
    return escaped


def _skills_in(line: str) -> tuple[str, ...]:
    return tuple(
        skill
        for skill, aliases in SKILLS.items()
        if any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in aliases)
    )


def _requirements(job: str) -> list[str]:
    """Keep job bullet points, plus unbulleted lines mentioning known tech."""
    found: list[str] = []
    for raw in job.splitlines():
        line = raw.strip()
        if not line:
            continue
        is_bullet = bool(BULLET.match(line))
        line = BULLET.sub("", line).strip()
        if (is_bullet or _skills_in(line)) and line:
            found.append(line)
    return found


def analyze_job(job: str, profile: str) -> list[Finding]:
    if not job.strip():
        raise ValueError("job description must not be empty")
    if not profile.strip():
        raise ValueError("profile must not be empty")

    evidence_lines = [
        (index, line.strip())
        for index, line in enumerate(profile.splitlines(), start=1)
        if line.strip() and not NEGATED.search(line)
    ]
    findings: list[Finding] = []
    for requirement in _requirements(job):
        skills = _skills_in(requirement)
        mentions: list[tuple[str, int, str]] = []
        missing: list[str] = []
        for skill in skills:
            evidence = next(
                ((number, line) for number, line in evidence_lines if skill in _skills_in(line)),
                None,
            )
            if evidence is None:
                missing.append(skill)
            else:
                mentions.append((skill, evidence[0], evidence[1]))
        status = (
            "manual-review"
            if not skills
            else "mentions-found"
            if not missing
            else "partial"
            if mentions
            else "no-mention"
        )
        findings.append(Finding(requirement, skills, tuple(mentions), tuple(missing), status))
    return findings


def render_job_review(job: str, profile: str, job_name: str, profile_name: str) -> str:
    findings = analyze_job(job, profile)
    statuses = ("mentions-found", "partial", "no-mention", "manual-review")
    counts = {status: sum(item.status == status for item in findings) for status in statuses}
    lines = [
        "# OpenCareerOps — Job Review",
        "",
        f"**Vacancy:** {_markdown(job_name)}",
        f"**Evidence source:** {_markdown(profile_name)}",
        "",
        "## Textual coverage (not a suitability score)",
        "",
        f"- All recognized terms mentioned: {counts['mentions-found']}",
        f"- Some recognized terms mentioned: {counts['partial']}",
        f"- No recognized terms mentioned in profile: {counts['no-mention']}",
        f"- Requires manual interpretation: {counts['manual-review']}",
        "",
        "## Requirements and evidence",
        "",
    ]
    if not findings:
        lines.append("No individual requirements extracted. Check the job description manually.")
    for number, item in enumerate(findings, start=1):
        label = {
            "mentions-found": "All terms mentioned",
            "partial": "Partial textual evidence",
            "no-mention": "No textual evidence",
            "manual-review": "Manual review required",
        }[item.status]
        lines.extend(
            [f"### {number}. {_markdown(item.requirement)}", "", f"**Result:** {label}", ""]
        )
        if item.skills:
            lines.append(f"**Recognized terms:** {', '.join(_markdown(s) for s in item.skills)}")
            lines.append("")
        for skill, line_number, line in item.mentions:
            lines.append(f"- {_markdown(skill)}: profile line {line_number} — {_markdown(line)}")
        if item.missing:
            missed = ", ".join(_markdown(skill) for skill in item.missing)
            lines.append(f"- Without a detected mention: {missed}")
        if not item.skills:
            lines.append("- No lexicon term detected; read and assess this requirement yourself.")
        lines.append("")
    lines.extend(
        [
            "## Next step",
            "",
            "Review unverified requirements against your actual work before editing a CV.",
            "A missing mention does not prove missing experience.",
            "A mention does not prove proficiency.",
            "No tasks, applications, or career-state records were created or modified.",
            "",
            "---",
            "",
            "*Deterministic text matching only; no LLM, external calls or decisions.*",
            "",
        ]
    )
    return "\n".join(lines)
