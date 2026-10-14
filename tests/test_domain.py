import unittest

from opencareerops.domain import ValidationError, parse_state


def valid_payload():
    return {
        "schema_version": 1,
        "focus": "Explore infrastructure engineering",
        "actions": [
            {"id": "a", "title": "Build demo", "status": "todo", "impact": 5, "urgency": 3, "effort": 2}
        ],
    }


class DomainTests(unittest.TestCase):
    def test_accepts_valid_state_and_defaults(self):
        state = parse_state(valid_payload())
        self.assertEqual(state.focus, "Explore infrastructure engineering")
        self.assertEqual(state.actions[0].category, "general")
        self.assertIsNone(state.actions[0].due_date)

    def test_rejects_duplicate_ids(self):
        payload = valid_payload()
        payload["actions"].append(dict(payload["actions"][0]))
        with self.assertRaisesRegex(ValidationError, "duplicate action id"):
            parse_state(payload)

    def test_rejects_boolean_ratings(self):
        payload = valid_payload()
        payload["actions"][0]["impact"] = True
        with self.assertRaisesRegex(ValidationError, "impact must be an integer"):
            parse_state(payload)

    def test_rejects_invalid_date_and_status(self):
        payload = valid_payload()
        payload["actions"][0]["due_date"] = "2026-02-30"
        with self.assertRaisesRegex(ValidationError, "valid date"):
            parse_state(payload)
        payload["actions"][0]["due_date"] = None
        payload["actions"][0]["status"] = "unknown"
        with self.assertRaisesRegex(ValidationError, "status must be one of"):
            parse_state(payload)

    def test_rejects_wrong_schema_version(self):
        payload = valid_payload()
        payload["schema_version"] = 2
        with self.assertRaisesRegex(ValidationError, "schema_version must be 1"):
            parse_state(payload)

    def test_rejects_empty_focus_and_nonarray_actions(self):
        payload = valid_payload()
        payload["focus"] = " "
        with self.assertRaisesRegex(ValidationError, "focus must be a non-empty"):
            parse_state(payload)
        payload["focus"] = "ok"
        payload["actions"] = {}
        with self.assertRaisesRegex(ValidationError, "actions must be an array"):
            parse_state(payload)
