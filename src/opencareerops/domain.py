"""Small validated domain contract, independent from a specific data source."""

from dataclasses import dataclass
from datetime import date
from typing import Any


class ValidationError(ValueError):
    """Input does not conform to the career state contract."""


STATUSES = frozenset({"todo", "in_progress", "blocked", "done"})


@dataclass(frozen=True)
class Action:
    id: str
    title: str
    status: str
    impact: int
    urgency: int
    effort: int
    category: str = "general"
    due_date: date | None = None


@dataclass(frozen=True)
class CareerState:
    focus: str
    actions: tuple[Action, ...]


def parse_date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a date in YYYY-MM-DD format")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValidationError(f"{field} must be a valid date in YYYY-MM-DD format") from error
    if parsed.isoformat() != value:
        raise ValidationError(f"{field} must be in YYYY-MM-DD format")
    return parsed


def _required_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _rating(value: Any, field: str) -> int:
    # bool is an int subclass, but True is not a meaningful rating.
    if type(value) is not int or not 1 <= value <= 5:
        raise ValidationError(f"{field} must be an integer from 1 to 5")
    return value


def parse_state(raw: Any) -> CareerState:
    if not isinstance(raw, dict):
        raise ValidationError("career state must be an object")
    if type(raw.get("schema_version")) is not int or raw["schema_version"] != 1:
        raise ValidationError("schema_version must be 1")
    focus = _required_string(raw.get("focus"), "focus")
    items = raw.get("actions")
    if not isinstance(items, list):
        raise ValidationError("actions must be an array")

    actions: list[Action] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        prefix = f"actions[{index}]"
        if not isinstance(item, dict):
            raise ValidationError(f"{prefix} must be an object")
        action_id = _required_string(item.get("id"), f"{prefix}.id")
        if action_id in seen:
            raise ValidationError(f"duplicate action id: {action_id}")
        seen.add(action_id)
        status = _required_string(item.get("status"), f"{prefix}.status")
        if status not in STATUSES:
            raise ValidationError(f"{prefix}.status must be one of: {', '.join(sorted(STATUSES))}")
        due_value = item.get("due_date")
        category_value = item.get("category", "general")
        actions.append(
            Action(
                id=action_id,
                title=_required_string(item.get("title"), f"{prefix}.title"),
                status=status,
                impact=_rating(item.get("impact"), f"{prefix}.impact"),
                urgency=_rating(item.get("urgency"), f"{prefix}.urgency"),
                effort=_rating(item.get("effort"), f"{prefix}.effort"),
                category=_required_string(category_value, f"{prefix}.category"),
                due_date=None if due_value is None else parse_date(due_value, f"{prefix}.due_date"),
            )
        )
    return CareerState(focus=focus, actions=tuple(actions))
