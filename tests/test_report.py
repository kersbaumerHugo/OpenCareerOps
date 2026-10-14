import unittest
from datetime import date

from opencareerops.domain import parse_state
from opencareerops.report import render_weekly_report


class ReportTests(unittest.TestCase):
    def test_render_is_deterministic_and_week_starts_monday(self):
        state = parse_state({"schema_version": 1, "focus": "Backend <script>alert(1)</script>",
                             "actions": [{"id": "x", "title": "Update [CV] | README", "status": "todo",
                                          "impact": 4, "urgency": 3, "effort": 2}]})
        report = render_weekly_report(state, date(2026, 10, 14))
        self.assertEqual(report, render_weekly_report(state, date(2026, 10, 14)))
        self.assertIn("**Week starting:** 2026-10-12", report)
        self.assertIn("&lt;script&gt;", report)
        self.assertIn(r"Update \[CV\] \| README", report)
        self.assertIn("Why: impact 4×3", report)

    def test_empty_and_blocked_only_has_guidance(self):
        state = parse_state({"schema_version": 1, "focus": "Test", "actions": []})
        self.assertIn("No actionable items", render_weekly_report(state, date(2026, 10, 14)))

    def test_shows_blocked_and_completed_separately(self):
        actions = [
            {"id": status, "title": status, "status": status, "impact": 3, "urgency": 3, "effort": 3}
            for status in ("done", "blocked")
        ]
        state = parse_state({"schema_version": 1, "focus": "Test", "actions": actions})
        report = render_weekly_report(state, date(2026, 10, 14))
        self.assertIn("## Completed", report)
        self.assertIn("## Blocked", report)
        self.assertIn("- Open: 0", report)

    def test_limit_rejects_zero(self):
        state = parse_state({"schema_version": 1, "focus": "Test", "actions": []})
        with self.assertRaisesRegex(ValueError, "at least 1"):
            render_weekly_report(state, date(2026, 10, 14), limit=0)
