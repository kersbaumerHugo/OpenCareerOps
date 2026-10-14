import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def run_cli(self, *arguments):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "opencareerops", *map(str, arguments)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_generates_report_with_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "report.md"
            process = self.run_cli(
                "--input",
                ROOT / "examples/fictional_career_state.json",
                "--output",
                output,
                "--today",
                "2026-10-14",
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn("Top priorities", output.read_text(encoding="utf-8"))

    def test_invalid_input_does_not_write_report(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "invalid.json"
            output = Path(directory) / "report.md"
            input_path.write_text(json.dumps({"schema_version": 2}), encoding="utf-8")
            process = self.run_cli(
                "--input", input_path, "--output", output, "--today", "2026-10-14"
            )
            self.assertEqual(process.returncode, 2)
            self.assertIn("schema_version", process.stderr)
            self.assertFalse(output.exists())

    def test_invalid_reference_date_returns_error(self):
        process = self.run_cli(
            "--input", ROOT / "examples/fictional_career_state.json", "--today", "2026-99-99"
        )
        self.assertEqual(process.returncode, 2)
        self.assertIn("today must be a valid date", process.stderr)
