"""Propose a career note from a *committed*, local Git repository.

No network, execution of project code, automatic vault edits, or claims of expertise.
A source locator is a commit-pinned repository file and line, not a credential.
"""

import html
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import yaml

from opencareerops.job_review import NEGATED, _skills_in
from opencareerops.vault import _body_and_metadata, _evidence_lines

MAX_SOURCES = 120
MAX_SOURCE_BYTES = 256 * 1024
MAX_TOTAL_BYTES = 1024 * 1024
MAX_EXCERPT_CHARS = 180
MAX_EXAMPLES_PER_TECH = 3
MAX_OUTCOMES = 14

_SENSITIVE_PATH = re.compile(
    r"(?:^|[._/-])(?:token|secret|password|credential|private|key)(?:[._/-]|$)",
    re.IGNORECASE,
)
_SECRET = re.compile(
    r"(?:password|passwd|api[_ -]?key|secret|access[_ -]?token|authorization|"
    r"private[_ -]?key|BEGIN [A-Z ]*PRIVATE KEY|AKIA[0-9A-Z]{16})",
    re.IGNORECASE,
)
_GITHUB_HTTPS = re.compile(r"^https://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")
_GITHUB_SSH = re.compile(r"^git@github\.com:([\w.-]+)/([\w.-]+?)(?:\.git)?$")
_TF_RESOURCE = re.compile(r'^\s*(?:resource|data|provider)\s+"(aws|azurerm|google)[_"\s]')
_TF_IAC = re.compile(r'^\s*(?:resource|data|provider|module|terraform)\s+["{]')
_COMPOSE = re.compile(r"^\s*(?:services|image|build):\s*(?:\S.*)?$")
_WORKFLOW = re.compile(r"^\s*(?:jobs|on|uses|runs-on):\s*(?:\S.*)?$")
_MARKDOWN_HEADING = re.compile(r"^\s*(#{1,6})\s+(.*)")
_PROSPECTIVE_SECTION = re.compile(
    r"^(?:goals?|objectives?|objetivos?|acceptance gates?|non[- ]?goals?|"
    r"architecture|arquitetura|roadmap|future|next steps|planned|planning|plans?)\b",
    re.IGNORECASE,
)
_OUTCOME = re.compile(
    r"\b(?:passed|failed|successful|rollback|no changes|recovered|executed|"
    r"operational|provisioned|validated|not demonstrated|not claimed|"
    r"exit code|limitation|unsupported|timeout)\b",
    re.IGNORECASE,
)
_CONTEXT = re.compile(r"^(?:Environment|Validation|Scope):\s*", re.IGNORECASE)
_FUTURE = re.compile(
    r"\b(?:todo|planned|planning|roadmap|future|next steps|"
    r"planejado|planejamento|próximos passos|proximos passos|"
    r"quero aprender|pretendo|will implement|will learn|plan to)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SourceMention:
    term: str
    path: str
    line: int
    excerpt: str
    kind: str


@dataclass(frozen=True)
class KnowledgeProposal:
    name: str
    revision: str
    repository_url: str | None
    sources_scanned: int
    mentions: tuple[SourceMention, ...]
    observations: tuple[SourceMention, ...]


def _git(root: Path, *arguments: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        capture_output=True,
        check=False,
        timeout=30,
    )
    if result.returncode:
        # Git stderr can contain local repository path or remote credentials.
        raise ValueError(
            f"git {arguments[0]} failed: check that --repo is a valid local Git checkout"
        )
    return result.stdout


def _canonical_github_remote(raw: str) -> str | None:
    match = _GITHUB_HTTPS.fullmatch(raw.strip()) or _GITHUB_SSH.fullmatch(raw.strip())
    if match is None:
        return None
    owner, repo = match.groups()
    if owner in {".", ".."} or repo in {".", ".."}:
        return None
    return f"https://github.com/{owner}/{repo}"


def _github_remote(root: Path) -> str | None:
    try:
        remote = _git(root, "config", "--get", "remote.origin.url").decode("utf-8").strip()
    except (ValueError, UnicodeDecodeError):
        return None
    return _canonical_github_remote(remote)


def _is_candidate(path: str) -> bool:
    parts = Path(path).parts
    if not parts or any(part in {".", ".."} for part in parts):
        return False
    if any(part.startswith(".") for part in parts) and not (
        len(parts) == 3 and parts[:2] == (".github", "workflows")
    ):
        return False
    lower = path.lower()
    if (
        _SECRET.search(path)
        or _SENSITIVE_PATH.search(path)
        or any(
            part in {"node_modules", "vendor", "dist", "build", "target", "archive"}
            for part in parts
        )
    ):
        return False
    name = parts[-1].lower()
    return bool(
        name == "readme.md"
        or (lower.startswith("docs/evidence/") and lower.endswith(".md"))
        or (lower.startswith(".github/workflows/") and name.endswith((".yml", ".yaml")))
        or lower.endswith(".tf")
        or name
        in {
            "compose.yaml",
            "compose.yml",
            "docker-compose.yml",
            "docker-compose.yaml",
            "dockerfile",
            "pyproject.toml",
        }
    )


def _code_mentions(path: str, content: str) -> list[SourceMention]:
    found: list[SourceMention] = []
    suffix = Path(path).suffix.lower()
    name = Path(path).name.lower()
    workflow = path.startswith(".github/workflows/")
    compose = name in {"compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml"}
    for number, source in enumerate(content.splitlines(), 1):
        line = source.strip()
        if (
            not line
            or line.startswith(("#", "//", "/*"))
            or _SECRET.search(line)
            or NEGATED.search(line)
            or _FUTURE.search(line)
        ):
            continue
        terms = list(_skills_in(line))
        if suffix == ".tf":
            match = _TF_RESOURCE.search(source)
            provider = {"aws": "AWS", "azurerm": "Azure", "google": "GCP"}
            if match and provider[match.group(1)] not in terms:
                terms.append(provider[match.group(1)])
            if _TF_IAC.search(source):
                terms.append("IaC (.tf)")
        if workflow and _WORKFLOW.search(source):
            terms.append("GitHub Actions (workflow)")
        if compose and _COMPOSE.search(source):
            terms.append("Docker Compose (configuration)")
        for term in dict.fromkeys(terms):
            found.append(SourceMention(term, path, number, line[:MAX_EXCERPT_CHARS], "config"))
    return found


def _markdown_mentions(path: str, content: str) -> list[SourceMention]:
    _, start = _body_and_metadata(content, path)
    # README goals and architecture diagrams are not evidence of implemented work.
    # Blank prospective sections without renumbering the original source lines.
    lines = content.splitlines()
    ignored_level: int | None = None
    for index in range(start, len(lines)):
        heading = _MARKDOWN_HEADING.match(lines[index])
        if heading:
            level = len(heading.group(1))
            if ignored_level is not None and level <= ignored_level:
                ignored_level = None
            if _PROSPECTIVE_SECTION.search(heading.group(2).strip()):
                ignored_level = level
        if ignored_level is not None:
            lines[index] = ""
    results: list[SourceMention] = []
    for line in _evidence_lines(lines, start, path):
        if _SECRET.search(line.text):
            continue
        for term in _skills_in(line.text):
            results.append(
                SourceMention(term, path, line.number, line.text[:MAX_EXCERPT_CHARS], "document")
            )
    return results


def _documented_outcomes(path: str, content: str) -> list[SourceMention]:
    """Quote reported checks and limits, but never convert them into proven outcomes."""
    observations: list[SourceMention] = []
    in_code = False
    for number, raw in enumerate(content.splitlines(), start=1):
        line = raw.strip()
        if line.startswith(("```", "~~~")):
            in_code = not in_code
            continue
        if (
            in_code
            or not line
            or line.startswith(("#", ">", "<!--"))
            or _SECRET.search(line)
            or _FUTURE.search(line)
        ):
            continue
        if _CONTEXT.search(line) or _OUTCOME.search(line):
            observations.append(
                SourceMention(
                    "Documented result", path, number, line[:MAX_EXCERPT_CHARS], "outcome"
                )
            )
    return observations


def inspect_git_project(root: Path) -> KnowledgeProposal:
    """Inspect committed blobs at HEAD, never the dirty working tree or untracked files."""
    if not root.is_dir():
        raise ValueError("repository must be an existing directory")
    root = root.resolve()
    actual = Path(_git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if actual != root:
        raise ValueError("--repo must point to the Git repository root")
    revision = _git(root, "rev-parse", "HEAD").decode("ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{40,64}", revision):
        raise ValueError("repository does not have a valid commit at HEAD")
    entries = _git(root, "ls-tree", "-r", "-z", "HEAD").split(b"\0")
    candidates: list[tuple[str, str]] = []
    for entry in entries:
        if not entry:
            continue
        header, raw_path = entry.split(b"\t", 1)
        mode, kind, oid = header.decode("ascii").split(" ")
        if mode not in {"100644", "100755"} or kind != "blob":
            continue  # no symlinks or submodules
        try:
            path = raw_path.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if _is_candidate(path):
            candidates.append((path, oid))
    if len(candidates) > MAX_SOURCES:
        raise ValueError(f"project exceeds {MAX_SOURCES} relevant tracked source files")
    # Review docs/evidence first, then real configuration and finally README summaries.
    candidates.sort(
        key=lambda pair: (
            0
            if pair[0].startswith("docs/evidence/")
            else 2
            if pair[0].lower().endswith("readme.md")
            else 1,
            pair[0],
        )
    )
    all_mentions: list[SourceMention] = []
    all_outcomes: list[SourceMention] = []
    byte_total = 0
    scanned = 0
    for path, oid in candidates:
        size_bytes = int(_git(root, "cat-file", "-s", oid))
        if size_bytes > MAX_SOURCE_BYTES:
            continue
        byte_total += size_bytes
        if byte_total > MAX_TOTAL_BYTES:
            raise ValueError("project exceeds 1 MiB bounded source scan")
        data = _git(root, "cat-file", "blob", oid)
        try:
            content = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            continue
        if content.startswith("version https://git-lfs.github.com/spec/v1"):
            continue
        scanned += 1
        if path.lower().endswith(".md"):
            all_mentions.extend(_markdown_mentions(path, content))
            if path.startswith("docs/evidence/"):
                all_outcomes.extend(_documented_outcomes(path, content))
        else:
            all_mentions.extend(_code_mentions(path, content))
    # Keep a small set of useful traceable signals; prevent overlong proposals.
    picked: list[SourceMention] = []
    counts: dict[str, int] = {}
    for match in all_mentions:
        if counts.get(match.term, 0) < MAX_EXAMPLES_PER_TECH:
            picked.append(match)
            counts[match.term] = counts.get(match.term, 0) + 1
    return KnowledgeProposal(
        root.name,
        revision,
        _github_remote(root),
        scanned,
        tuple(picked),
        tuple(all_outcomes[:64]),
    )


def _escape(value: str) -> str:
    escaped = html.escape(value.replace("\r", " ").replace("\n", " "), quote=False)
    for character in ("\\", "`", "*", "_", "[", "]", "|"):
        escaped = escaped.replace(character, "\\" + character)
    return escaped


def render_knowledge_proposal(proposal: KnowledgeProposal) -> str:
    """Generate an opt-out draft; it is NOT approved career evidence."""
    frontmatter = {
        "type": "project",
        "status": "proposed",
        "career_evidence": False,
        "source_repo": proposal.repository_url or "local-git-checkout",
        "source_commit": proposal.revision,
    }
    lines = [
        "---",
        yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).strip(),
        "---",
        "",
        f"# {_escape(proposal.name)} — proposta para revisão",
        "",
        "> **Não aprovado.** Menções e arquivos versionados não comprovam autoria, execução, "
        "domínio técnico ou resultados.",
        "> Revise cada evidência antes de mover esta nota para o Obsidian e mudar "
        "`career_evidence` para `true`.",
        "",
        "## Proveniência",
        "",
        f"- Commit examinado: `{proposal.revision}`",
        f"- Arquivos candidatos lidos: {proposal.sources_scanned}",
        "- Origem: somente blobs versionados no commit (sem arquivos locais não commitados)",
        "",
        "## Evidências candidatas",
        "",
    ]
    if not proposal.mentions:
        lines.append("Nenhuma menção reconhecida nos arquivos permitidos. Faça revisão manual.")
        lines.append("")
    if proposal.observations:
        lines.extend(
            [
                "## Registros documentados de validação e limitações",
                "",
                "Relatos dos arquivos de evidência, **não verificados independentemente**.",
                "Conferir ambiente, autoria e resultados antes de aproveitar no currículo.",
                "",
            ]
        )
        for item in proposal.observations[:MAX_OUTCOMES]:
            locator = f"{item.path}:L{item.line}"
            if proposal.repository_url:
                path = quote(item.path, safe="/")
                url = f"{proposal.repository_url}/blob/{proposal.revision}/{path}#L{item.line}"
                source_ref = f"[{_escape(locator)}]({url})"
            else:
                source_ref = f"`{_escape(locator)}`"
            lines.append(f"- {source_ref}: {_escape(item.excerpt)}")
        lines.append("")
    groups: dict[str, list[SourceMention]] = {}
    for item in proposal.mentions:
        groups.setdefault(item.term, []).append(item)
    for term in sorted(groups, key=str.casefold):
        lines.extend([f"### {_escape(term)}", ""])
        for item in groups[term]:
            locator = f"{item.path}:L{item.line}"
            if proposal.repository_url:
                path = quote(item.path, safe="/")
                url = f"{proposal.repository_url}/blob/{proposal.revision}/{path}#L{item.line}"
                source_ref = f"[{_escape(locator)}]({url})"
            else:
                source_ref = f"`{_escape(locator)}`"
            tag = "configuração versionada" if item.kind == "config" else "documentação"
            lines.append(f"- {source_ref} ({tag}): {_escape(item.excerpt)}")
        lines.append("")
    lines.extend(
        [
            "## Revisão humana obrigatória",
            "",
            "- [ ] Confirmar minha contribuição específica "
            "(não presumir autoria pelo repositório).",
            "- [ ] Diferenciar recursos provisionados, testes em emuladores e nuvem real; "
            "verificar resultados.",
            "",
            "## Uso no CareerOps",
            "",
            "Após revisar e corrigir, salve esta nota em `Projects/` no cofre privado e altere",
            "`career_evidence: false` para `true`. Antes disso, o Vault Reader a ignora.",
            "Nenhuma tarefa ou candidatura foi criada.",
            "",
        ]
    )
    return "\n".join(lines)
