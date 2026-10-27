"""Evidence curation from committed Git signals into reviewable, attributed claims.

This module intentionally does not infer authorship, cloud parity, or expertise.
It only groups already extracted, commit-pinned source lines into a short draft.
"""

import re
from dataclasses import dataclass
from urllib.parse import quote

import yaml

from opencareerops.knowledge import KnowledgeProposal, SourceMention, _escape

MAX_CURATED_ITEMS = 5
MAX_SOURCES_PER_ITEM = 3
MAX_LIMITATIONS = 3


@dataclass(frozen=True)
class CuratedItem:
    title: str
    assessment: str
    sources: tuple[SourceMention, ...]


def _choose(
    evidence: tuple[SourceMention, ...],
    predicate: re.Pattern[str],
    *,
    maximum: int = MAX_SOURCES_PER_ITEM,
) -> tuple[SourceMention, ...]:
    """Find a few distinct references, prioritizing unique relevant files."""
    matches = [line for line in evidence if predicate.search(line.excerpt)]
    unique: list[SourceMention] = []
    paths: set[str] = set()
    for match in matches:
        if match.path not in paths:
            unique.append(match)
            paths.add(match.path)
        if len(unique) == maximum:
            return tuple(unique)
    for match in matches:
        if match not in unique:
            unique.append(match)
        if len(unique) == maximum:
            break
    return tuple(unique)


def _keep(
    *sequences: tuple[SourceMention, ...], limit: int = MAX_SOURCES_PER_ITEM
) -> tuple[SourceMention, ...]:
    return tuple(dict.fromkeys(item for seq in sequences for item in seq))[:limit]


def curate_project(proposal: KnowledgeProposal) -> tuple[CuratedItem, ...]:
    """Conservatively group supporting excerpts; never manufacture achievements."""
    found: list[CuratedItem] = []
    observed = proposal.observations
    code = tuple(item for item in proposal.mentions if item.kind == "config")

    infra = _choose(code, re.compile(r'\bresource\s+"(?:aws|azurerm|google)_', re.I), maximum=2)
    if infra:
        found.append(
            CuratedItem(
                "Infraestrutura declarada como código",
                "O repositório contém definições de recursos de infraestrutura. "
                "Isso demonstra configuração versionada, não provisionamento em produção.",
                infra,
            )
        )

    provision = _choose(
        observed,
        re.compile(
            r"\b(?:provisioned|user.?data bootstrap executed|"
            r"http health endpoint operational|reconciliation: no changes)\b",
            re.I,
        ),
    )
    if provision:
        found.append(
            CuratedItem(
                "Provisionamento e verificações documentados",
                "Registros do projeto relatam execução ou verificação do ambiente. "
                "Resultado e escopo precisam de confirmação humana.",
                provision,
            )
        )

    # A rollback claim needs an actual rollback outcome. Generic README plans do not count.
    rollback = _choose(
        observed,
        re.compile(r"\b(?:automatic rollback|rollback: successful|recovered version)\b", re.I),
        maximum=2,
    )
    failure = _choose(
        observed,
        re.compile(r"\b(?:functional smoke: failed|deployment exit code: 1)\b", re.I),
        maximum=1,
    )
    if rollback:
        found.append(
            CuratedItem(
                "Experimento de falha e recuperação relatado",
                "Há um registro de rollback/recuperação; conferir o teste e o ambiente "
                "antes de descrever isso como capacidade operacional.",
                _keep(failure, rollback),
            )
        )

    ci = tuple(
        item
        for item in code
        if item.path.startswith(".github/workflows/")
        and (
            item.term == "GitHub Actions (workflow)"
            or re.search(r"(?:^|\s)(?:jobs:|runs-on:)", item.excerpt)
        )
    )
    if ci:
        found.append(
            CuratedItem(
                "Pipeline de CI versionado",
                "O repositório contém configuração de GitHub Actions. "
                "A presença do workflow não prova que sua execução passou.",
                ci[:MAX_SOURCES_PER_ITEM],
            )
        )

    compose = tuple(item for item in code if item.term == "Docker Compose (configuration)")
    if compose:
        found.append(
            CuratedItem(
                "Serviços descritos em Docker Compose",
                "Arquivos Compose definem serviços. Não é confirmação de deploy ou operação.",
                compose[:MAX_SOURCES_PER_ITEM],
            )
        )

    # Only offer generic fallback if there are relevant signals but none of the specific ones.
    if not found and proposal.mentions:
        found.append(
            CuratedItem(
                "Tecnologias mencionadas ou configuradas",
                "O repositório contém referências às tecnologias abaixo. "
                "O contexto e a contribuição pessoal ainda não foram verificados.",
                proposal.mentions[:MAX_SOURCES_PER_ITEM],
            )
        )
    return tuple(found[:MAX_CURATED_ITEMS])


_LIMITATION = re.compile(
    r"\b(?:not (?:validated|demonstrated|claimed|implemented|supported|establish)|"
    r"failed because|not verified|limitation|unsupported|does not establish|"
    r"não (?:validado|demonstrado|implementado))\b",
    re.IGNORECASE,
)
_ENVIRONMENT = re.compile(
    r"(?:\bEnvironment:|\bValidation:|\blocal.?emulator\b|\bfloci\b|\bsimulated\b)",
    re.I,
)


def _reference(proposal: KnowledgeProposal, mention: SourceMention) -> str:
    label = _escape(f"{mention.path}:L{mention.line}")
    if not proposal.repository_url:
        return f"`{label}`"
    path = quote(mention.path, safe="/")
    url = f"{proposal.repository_url}/blob/{proposal.revision}/{path}#L{mention.line}"
    return f"[{label}]({url})"


def render_curated_proposal(proposal: KnowledgeProposal) -> str:
    """Return a compact *unapproved* Obsidian note with source-level citations."""
    items = curate_project(proposal)
    limits = _choose(proposal.observations, _LIMITATION, maximum=MAX_LIMITATIONS)
    environments = _choose(proposal.observations, _ENVIRONMENT, maximum=2)
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
        f"# {_escape(proposal.name)} — síntese candidata",
        "",
        "> **Não aprovado.** Este texto agrupa sinais de arquivos commitados; "
        "não comprova autoria, execução real, senioridade ou impacto.",
        "> Verifique cada afirmação e não remova `career_evidence: false` "
        "antes da aprovação humana.",
        "",
        "## Proveniência e escopo",
        "",
        f"- Commit: `{proposal.revision}`",
        f"- Arquivos examinados: {proposal.sources_scanned}",
        "- Dados: somente arquivos commitados, sem execução de código nem chamadas de rede.",
        "",
    ]
    if environments:
        lines.append("**Contexto declarado nos arquivos:**")
        for source in environments:
            lines.append(f"- {_reference(proposal, source)}: {_escape(source.excerpt)}")
        lines.append("")
    else:
        lines.extend(["**Ambiente de execução:** não confirmado automaticamente.", ""])

    lines.extend(["## Realizações candidatas para revisão", ""])
    if not items:
        lines.extend(
            [
                "Nenhuma evidência suficiente para uma afirmação candidata. "
                "Consulte os arquivos do projeto manualmente.",
                "",
            ]
        )
    for index, item in enumerate(items, start=1):
        lines.extend([f"### {index}. {_escape(item.title)}", "", _escape(item.assessment), ""])
        for source in item.sources:
            lines.append(f"- {_reference(proposal, source)}: {_escape(source.excerpt)}")
        lines.append("")

    lines.extend(["## Limitações documentadas", ""])
    if limits:
        for limit in limits:
            lines.append(f"- {_reference(proposal, limit)}: {_escape(limit.excerpt)}")
    else:
        lines.append(
            "Nenhuma limitação localizada na amostra; isto **não** comprova ausência de limitações."
        )
    lines.extend(
        [
            "",
            "## Confirmação humana",
            "",
            "- [ ] Confirmar o que implementei pessoalmente.",
            "- [ ] Confirmar testes, resultados e ambiente (emulação ≠ nuvem real).",
            "- [ ] Ajustar o texto para refletir apenas conquistas verificadas.",
            "- [ ] Conferir os links e a ausência de dados sensíveis.",
            "",
            "Após revisar, copie para o cofre privado em `Projects/` e aprove "
            "alterando `career_evidence` para `true`.",
            "Nenhum arquivo do cofre foi modificado e nenhuma candidatura foi enviada.",
            "",
        ]
    )
    return "\n".join(lines)
