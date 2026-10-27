"""Cover CLI routing and failures without hiding execution in unmeasured subprocesses."""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from opencareerops.cli import main


class InProcessCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.state = self.directory / "state.json"
        self.job = self.directory / "job.txt"
        self.profile = self.directory / "profile.md"
        self.state.write_text(
            json.dumps({"schema_version": 1, "focus": "Platform", "actions": []}),
            encoding="utf-8",
        )
        self.job.write_text("- Python and AWS\n- Communication", encoding="utf-8")
        self.profile.write_text("Developed Python automation", encoding="utf-8")

    def invoke(self, *args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = main(list(map(str, args)))
        return result, stdout.getvalue(), stderr.getvalue()

    def test_weekly_review_success(self):
        output = self.directory / "reports" / "weekly.md"
        code, stdout, stderr = self.invoke(
            "--input", self.state, "--output", output, "--today", "2026-10-14"
        )
        self.assertEqual(code, 0, stderr)
        self.assertIn("Report written", stdout)
        self.assertIn("## Top priorities", output.read_text(encoding="utf-8"))

    def test_weekly_review_invalid_limit_and_date(self):
        output = self.directory / "weekly.md"
        for extra, message in [
            (("--limit", "0"), "limit must be at least 1"),
            (("--today", "bad-date"), "today must be a valid date"),
        ]:
            with self.subTest(extra=extra):
                code, stdout, stderr = self.invoke(
                    "--input", self.state, "--output", output, *extra
                )
                self.assertEqual(code, 2)
                self.assertEqual(stdout, "")
                self.assertIn(message, stderr)
                self.assertFalse(output.exists())

    def test_weekly_review_invalid_json_and_state(self):
        output = self.directory / "weekly.md"
        for content, expected in [
            ("{bad", "error:"),
            ('{"schema_version": 2}', "schema_version must be 1"),
        ]:
            with self.subTest(content=content):
                self.state.write_text(content, encoding="utf-8")
                code, _, stderr = self.invoke("--input", self.state, "--output", output)
                self.assertEqual(code, 2)
                self.assertIn(expected, stderr)
                self.assertFalse(output.exists())

    def test_weekly_review_missing_input(self):
        code, _, stderr = self.invoke("--input", self.directory / "absent.json")
        self.assertEqual(code, 2)
        self.assertIn("error:", stderr)

    def test_job_review_success(self):
        output = self.directory / "reports" / "job.md"
        code, stdout, stderr = self.invoke(
            "job-review",
            "--job",
            self.job,
            "--profile",
            self.profile,
            "--output",
            output,
        )
        self.assertEqual(code, 0, stderr)
        self.assertIn("Job review written", stdout)
        report = output.read_text(encoding="utf-8")
        self.assertIn("profile line 1", report)
        self.assertIn("Without a detected mention: AWS", report)

    def test_job_review_empty_profile(self):
        self.profile.write_text(" ", encoding="utf-8")
        output = self.directory / "job.md"
        code, _, stderr = self.invoke(
            "job-review",
            "--job",
            self.job,
            "--profile",
            self.profile,
            "--output",
            output,
        )
        self.assertEqual(code, 2)
        self.assertIn("profile must not be empty", stderr)
        self.assertFalse(output.exists())

    def test_job_review_missing_job_file(self):
        code, _, stderr = self.invoke(
            "job-review",
            "--job",
            self.directory / "missing.txt",
            "--profile",
            self.profile,
        )
        self.assertEqual(code, 2)
        self.assertIn("error:", stderr)

    def test_job_review_cannot_write_output(self):
        code, _, stderr = self.invoke(
            "job-review",
            "--job",
            self.job,
            "--profile",
            self.profile,
            "--output",
            self.directory,
        )
        self.assertEqual(code, 2)
        self.assertIn("error:", stderr)

    def test_main_without_explicit_argv_uses_sys_argv(self):
        output = self.directory / "default-argv.md"
        with patch.object(
            sys,
            "argv",
            ["opencareerops", "--input", str(self.state), "--output", str(output)],
        ):
            code, _, stderr = self.invoke_default()
        self.assertEqual(code, 0, stderr)
        self.assertTrue(output.exists())

    @staticmethod
    def invoke_default():
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = main()
        return result, stdout.getvalue(), stderr.getvalue()
