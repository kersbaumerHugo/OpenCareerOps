"""Read an explicitly scoped Obsidian Markdown vault without writing to it.

This is a textual evidence *reader*, not a career history verifier or a task database.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from opencareerops.job_review import NEGATED, _markdown, _requirements, _skills_in

ALLOWED_FOLDERS = ("Career", "Projects", "Evidence", "Learning")
MAX_NOTE_BYTES = 1024 * 1024
MAX_NOTES = 500
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
_HEADING = re.compile(r"^\s*(#{1,6})\s+(.*)")
_IGNORE_HEADING = re.compile(
    r"\b(?:roadmap|next steps|todo|to do|planned|planning|future|ideas|ideas for|"
    r"próximos passos|proximos passos|planejado|planejamento|ideias|pendências|pendencias|"
    r"objetivos futuros)\b",
    re.IGNORECASE,
)
_FUTURE = re.compile(
    r"\b(?:pretendo|planejo|planejamos|planejado|quero aprender|quero usar|"
    r"vou estudar|vou implementar|we plan to|planning to|plan to|will learn)\b",
    re.IGNORECASE,
)
_CHECKBOX = re.compile(r"^\s*[-*]\s+\[[ xX]\]\s+")


@dataclass(frozen=True)
class VaultLine:
    """A plain-text mention and its original Markdown source line."""

    path: str
    number: int
    text: str


@dataclass(frozen=True)
class VaultNote:
    path: str
    metadata: dict[str, Any]
    evidence: tuple[VaultLine, ...]


def _body_and_metadata(text: str, path: str) -> tuple[dict[str, Any], int]:
    """Parse Obsidian-style YAML frontmatter. Return first body line (0-based)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, 0
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ValueError(f"{path}: YAML frontmatter has no closing ---")
    try:
        metadata = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as error:
        raise ValueError(f"{path}: invalid YAML frontmatter") from error
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict) or any(not isinstance(k, str) for k in metadata):
        raise ValueError(f"{path}: YAML frontmatter must be a mapping with string keys")
    return metadata, end + 1


def _evidence_lines(lines: list[str], start: int, relative_path: str) -> tuple[VaultLine, ...]:
    matches = []
    fence_char: str | None = None
    ignored_heading_level: int | None = None
    for index in range(start, len(lines)):
        stripped = lines[index].strip()
        fence = _FENCE.match(stripped)
        if fence:
            marker = fence.group(1)
            if fence_char is None:
                fence_char = marker[0]
            elif fence_char == marker[0]:
                fence_char = None
            continue
        if fence_char is not None:
            continue
        heading = _HEADING.match(stripped)
        if heading:
            level = len(heading.group(1))
            if ignored_heading_level is not None and level <= ignored_heading_level:
                ignored_heading_level = None
            if _IGNORE_HEADING.search(heading.group(2)):
                ignored_heading_level = level
            continue
        if (
            ignored_heading_level is not None
            or not stripped
            or stripped.startswith((">", "<!--"))
            or _CHECKBOX.match(stripped)
            or NEGATED.search(stripped)
            or _FUTURE.search(stripped)
        ):
            continue
        if _skills_in(stripped):
            matches.append(VaultLine(relative_path, index + 1, stripped))
    return tuple(matches)


def read_vault(root: Path) -> tuple[VaultNote, ...]:
    """Only scan named top-level career folders; ignore symlinks and hidden directories."""
    if not root.is_dir():
        raise ValueError(f"vault must be an existing directory: {root}")
    root = root.resolve()
    notes: list[VaultNote] = []
    for folder in ALLOWED_FOLDERS:
        top = root / folder
        if top.is_symlink() or not top.is_dir():
            continue
        for file in sorted(top.rglob("*.md")):
            if file.is_symlink() or any(
                part.startswith(".") for part in file.relative_to(root).parts
            ):
                continue
            # Defense-in-depth against a path or a directory redirected outside the vault.
            if not file.is_file() or not file.resolve().is_relative_to(root):
                continue
            relative = file.relative_to(root).as_posix()
            if file.stat().st_size > MAX_NOTE_BYTES:
                raise ValueError(f"{relative}: Markdown note exceeds 1 MiB limit")
            if len(notes) >= MAX_NOTES:
                raise ValueError("vault exceeds 500 readable Markdown notes")
            content = file.read_text(encoding="utf-8-sig")
            metadata, start = _body_and_metadata(content, relative)
            # Explicit opt-out for notes that should never be used in career reviews.
            if metadata.get("career_evidence") is False:
                continue
            notes.append(
                VaultNote(
                    relative,
                    metadata,
                    _evidence_lines(content.splitlines(), start, relative),
                )
            )
    return tuple(notes)


def render_vault_job_review(
    job: str,
    notes: tuple[VaultNote, ...],
    job_name: str,
    *,
    profile: str | None = None,
    profile_name: str | None = None,
) -> str:
    """Emit review with reproducible file:line mentions; no edits to vault or tasks."""
    if not job.strip():
        raise ValueError("job description must not be empty")
    if profile is not None and not profile.strip():
        raise ValueError("profile must not be empty")
    sources = [line for note in notes for line in note.evidence]
    if profile is not None:
        name = profile_name or "profile"
        for index, line in enumerate(profile.splitlines(), start=1):
            if _skills_in(line) and not NEGATED.search(line) and not _FUTURE.search(line):
                sources.append(VaultLine(name, index, line.strip()))

    found = _requirements(job)
    counts = {"all": 0, "partial": 0, "none": 0, "manual": 0}
    blocks: list[str] = []
    for index, requirement in enumerate(found, start=1):
        skills = _skills_in(requirement)
        groups = {
            skill: [source for source in sources if skill in _skills_in(source.text)][:3]
            for skill in skills
        }
        missing = [skill for skill in skills if not groups[skill]]
        if not skills:
            counts["manual"] += 1
            category = "Manual review required"
        elif not missing:
            counts["all"] += 1
            category = "All terms mentioned"
        elif len(missing) == len(skills):
            counts["none"] += 1
            category = "No textual evidence"
        else:
            counts["partial"] += 1
            category = "Partial textual evidence"
        blocks.extend([f"### {index}. {_markdown(requirement)}", "", f"**Result:** {category}", ""])
        for skill, matching in groups.items():
            for match in matching:
                blocks.append(
                    f"- {_markdown(skill)}: {_markdown(match.path)}:L{match.number} — "
                    f"{_markdown(match.text)}"
                )
        if missing:
            blocks.append("- Without a detected mention: " + ", ".join(missing))
        if not skills:
            blocks.append("- No lexicon term detected; assess this requirement manually.")
        blocks.append("")

    result = [
        "# OpenCareerOps — Vault Job Review",
        "",
        f"**Vacancy:** {_markdown(job_name)}",
        f"**Markdown notes scanned:** {len(notes)}",
        f"**Evidence-bearing lines:** {len(sources)}",
        "",
        "## Textual coverage (not a suitability score)",
        "",
        f"- All recognized terms mentioned: {counts['all']}",
        f"- Some recognized terms mentioned: {counts['partial']}",
        f"- No recognized terms mentioned: {counts['none']}",
        f"- Requires manual interpretation: {counts['manual']}",
        "",
        "## Requirements and evidence",
        "",
    ]
    result.extend(blocks or ["No requirements extracted; review the vacancy manually.", ""])
    result.extend(
        [
            "## Notes",
            "",
            "Text mentions are not proof of practical experience, seniority, or proficiency.",
            "Absence of a mention is not evidence of a missing skill.",
            "Plans, checkboxes, code, negations and YAML metadata are filtered heuristically.",
            "Check cited notes and repositories before using statements in a CV.",
            "This command reads only; it does not create tasks, apply or edit the vault.",
            "",
        ]
    )
    return "\n".join(result)
