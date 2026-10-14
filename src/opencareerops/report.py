"""Pure Markdown rendering: no network, persistence or side effects."""

import html
from datetime import date, timedelta

from opencareerops.domain import STATUSES, CareerState
from opencareerops.priorities import rank_actions


def _md(value: str) -> str:
    """Keep external text safely inline in Markdown rather than treating it as markup."""
    text = html.escape(value.replace("\r", " ").replace("\n", " "), quote=False)
    for char in ("\\", "`", "*", "_", "[", "]", "|"):
        # Backslash must be escaped first so later escapes are not double-escaped.
        text = text.replace(char, "\\" + char)
    return text


def render_weekly_report(state: CareerState, today: date, limit: int = 5) -> str:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    week_start = today - timedelta(days=today.weekday())
    counts = {status: sum(a.status == status for a in state.actions) for status in STATUSES}
    ranked = rank_actions(state, today)

    lines = [
        "# OpenCareerOps — Weekly Career Review",
        "",
        f"**Week starting:** {week_start.isoformat()}",
        f"**Focus:** {_md(state.focus)}",
        "",
        "## Career state",
        "",
        f"- Open: {counts['todo'] + counts['in_progress']}",
        f"- In progress: {counts['in_progress']}",
        f"- Blocked: {counts['blocked']}",
        f"- Done: {counts['done']}",
        "",
        "## Top priorities",
        "",
    ]
    if not ranked:
        lines.append("No actionable items. Review blocked tasks and add next steps.")
    else:
        for position, item in enumerate(ranked[:limit], 1):
            action = item.action
            due = action.due_date.isoformat() if action.due_date else "no due date"
            lines.extend(
                [
                    f"{position}. **{_md(action.title)}** — score **{item.score}** "
                    f"(category: {_md(action.category)}; due: {due}; status: {action.status})",
                    f"   - Why: {item.explanation}",
                ]
            )
        if len(ranked) > limit:
            lines.extend(["", f"{len(ranked) - limit} additional open item(s) not shown."])

    blocked = sorted((a for a in state.actions if a.status == "blocked"), key=lambda a: a.id)
    if blocked:
        lines.extend(["", "## Blocked", ""])
        lines.extend(f"- {_md(a.title)} (ID: {_md(a.id)})" for a in blocked)

    done = sorted((a for a in state.actions if a.status == "done"), key=lambda a: a.id)
    if done:
        lines.extend(["", "## Completed (snapshot)", ""])
        lines.extend(f"- {_md(a.title)} (ID: {_md(a.id)})" for a in done)

    lines.extend(
        [
            "",
            "---",
            "",
            "*Recommendations are deterministic suggestions; final decisions require human review.*",
            "",
        ]
    )
    return "\n".join(lines)
