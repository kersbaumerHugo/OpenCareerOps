import unittest
from datetime import date

from opencareerops.domain import parse_state
from opencareerops.priorities import rank_actions


def action(action_id, *, status="todo", due=None, impact=3, urgency=3, effort=3):
    return {
        "id": action_id,
        "title": action_id,
        "status": status,
        "impact": impact,
        "urgency": urgency,
        "effort": effort,
        "due_date": due,
    }


class PriorityTests(unittest.TestCase):
    def test_overdue_and_due_soon_explain_bonuses(self):
        state = parse_state(
            {
                "schema_version": 1,
                "focus": "Test",
                "actions": [
                    action("later", due="2026-11-01"),
                    action("soon", due="2026-10-21"),
                    action("overdue", due="2026-10-13"),
                ],
            }
        )
        ranked = rank_actions(state, date(2026, 10, 14))
        self.assertEqual([a.action.id for a in ranked], ["overdue", "soon", "later"])
        self.assertIn("overdue +4", ranked[0].explanation)
        self.assertIn("within 7 days +2", ranked[1].explanation)

    def test_blocked_and_done_are_not_ranked(self):
        state = parse_state(
            {
                "schema_version": 1,
                "focus": "Test",
                "actions": [
                    action("a", status="blocked"),
                    action("b", status="done"),
                    action("c", status="in_progress"),
                ],
            }
        )
        ranked = rank_actions(state, date(2026, 10, 14))
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].action.id, "c")
        self.assertIn("in progress +1", ranked[0].explanation)

    def test_ties_break_by_nearest_due_date_then_id(self):
        state = parse_state(
            {
                "schema_version": 1,
                "focus": "Test",
                "actions": [
                    action("z"),
                    action("b", due="2026-12-02"),
                    action("a", due="2026-12-02"),
                ],
            }
        )
        self.assertEqual(
            [r.action.id for r in rank_actions(state, date(2026, 10, 14))], ["a", "b", "z"]
        )
