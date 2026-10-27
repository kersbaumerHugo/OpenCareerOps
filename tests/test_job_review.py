import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from opencareerops.job_review import analyze_job, render_job_review


class JobReviewTests(unittest.TestCase):
    def test_partial_evidence_has_traceable_line_numbers(self):
        job = (
            "Requisitos:\n- Experiência em Python, AWS e Docker\n- Kubernetes\n- Comunicação clara"
        )
        profile = "Engenheiro de software\nPython em automações\nDocker em projetos"
        results = analyze_job(job, profile)
        self.assertEqual([r.status for r in results], ["partial", "no-mention", "manual-review"])
        self.assertEqual(results[0].missing, ("AWS",))
        self.assertEqual(results[0].mentions[0], ("Python", 2, "Python em automações"))
        self.assertEqual(results[0].mentions[1], ("Docker", 3, "Docker em projetos"))

    def test_matches_alias_and_avoids_substring(self):
        results = analyze_job("- K8s e Git", "Experiência com Kubernetes\nDigitalizar tarefas")
        self.assertEqual(results[0].missing, ("Git",))
        self.assertEqual(results[0].mentions[0][0], "Kubernetes")

    def test_no_experience_claim_is_not_accepted(self):
        results = analyze_job("- AWS", "Não tenho AWS\nEstudando AWS")
        self.assertEqual(results[0].status, "no-mention")

    def test_report_escapes_untrusted_markdown_and_html(self):
        result = render_job_review(
            "- Python <script>alert(1)</script>",
            "Experiência [Python] | automações",
            "<vaga>",
            "perfil.md",
        )
        self.assertIn("&lt;script&gt;", result)
        self.assertIn("**Vacancy:** &lt;vaga&gt;", result)
        self.assertIn(r"Experiência \[Python\] \| automações", result)
        self.assertNotIn("<script>", result)

    def test_empty_rejected_and_no_extracted_items_is_explicit(self):
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            analyze_job("", "Python")
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            analyze_job("- Docker", "")
        report = render_job_review("Olá, somos uma empresa", "Python", "vaga", "cv")
        self.assertIn("No individual requirements extracted", report)

    def test_deterministic_report(self):
        args = ("- Python\n- AWS", "Python", "vaga", "cv")
        self.assertEqual(render_job_review(*args), render_job_review(*args))


class JobReviewCLITests(unittest.TestCase):
    def test_end_to_end_with_fictional_files(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.md"
            env = dict(os.environ)
            env["PYTHONPATH"] = str(root / "src")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "opencareerops",
                    "job-review",
                    "--job",
                    str(root / "examples/fictional_job.txt"),
                    "--profile",
                    str(root / "examples/fictional_profile.md"),
                    "--output",
                    str(output),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("## Requirements and evidence", output.read_text(encoding="utf-8"))

    def test_empty_profile_does_not_write_report(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "profile.md"
            profile.write_text("  ", encoding="utf-8")
            output = Path(directory) / "report.md"
            env = dict(os.environ)
            env["PYTHONPATH"] = str(root / "src")
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "opencareerops",
                    "job-review",
                    "--job",
                    str(root / "examples/fictional_job.txt"),
                    "--profile",
                    str(profile),
                    "--output",
                    str(output),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("profile must not be empty", proc.stderr)
            self.assertFalse(output.exists())
