"""Deterministic, explainable ranking. No LLM or opaque scoring."""

from dataclasses import dataclass
from datetime import date

from opencareerops.domain import Action, CareerState


@dataclass(frozen=True)
class RankedAction:
    action: Action
    score: int
    explanation: str


def rank_actions(state: CareerState, today: date) -> list[RankedAction]:
    ranked: list[RankedAction] = []
    for action in state.actions:
        if action.status not in {"todo", "in_progress"}:
            continue
        score = action.impact * 3 + action.urgency * 2 - action.effort
        reasons = [
            f"impact {action.impact}×3",
            f"urgency {action.urgency}×2",
            f"effort −{action.effort}",
        ]
        if action.due_date is not None:
            days_remaining = (action.due_date - today).days
            if days_remaining < 0:
                score += 4
                reasons.append("overdue +4")
            elif days_remaining <= 7:
                score += 2
                reasons.append("due within 7 days +2")
        if action.status == "in_progress":
            score += 1
            reasons.append("in progress +1")
        ranked.append(RankedAction(action, score, "; ".join(reasons)))

    return sorted(
        ranked,
        key=lambda item: (-item.score, item.action.due_date or date.max, item.action.id),
    )
