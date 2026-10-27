"""Vault integration tests: privacy boundary, exact provenance and legacy compatibility."""

import tempfile
import unittest
from pathlib import Path

from opencareerops.vault import read_vault, render_vault_job_review


class VaultReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for folder in ("Career", "Projects", "Evidence", "Learning", "00-Inbox", ".obsidian"):
            (self.root / folder).mkdir()

    def write(self, name: str, content: str) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_reads_approved_folders_preserving_source_line(self):
        self.write(
            "Projects/demo.md",
            "---\ntype: project\nstatus: active\ntags: [python, devops]\n---\n"
            "# Fictional project\nImplemented Python APIs using Docker.\n",
        )
        notes = read_vault(self.root)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].metadata["type"], "project")
        self.assertEqual(notes[0].evidence[0].path, "Projects/demo.md")
        self.assertEqual(notes[0].evidence[0].number, 7)
        self.assertIn("Docker", notes[0].evidence[0].text)
        review = render_vault_job_review("- Python, Docker and AWS", notes, "vaga.txt")
        self.assertIn("Projects/demo.md:L7", review)
        self.assertIn("Without a detected mention: AWS", review)
        self.assertIn("Partial textual evidence", review)

    def test_ignores_inbox_hidden_config_and_explicit_opt_out(self):
        self.write("00-Inbox/idea.md", "AWS roadmap")
        self.write(".obsidian/plugins/trap.md", "AWS")
        self.write("Projects/.secret.md", "AWS")
        self.write("Projects/private.md", "---\ncareer_evidence: false\n---\nAWS in a note")
        self.write("Projects/approved.md", "Use Docker in practice")
        notes = read_vault(self.root)
        self.assertEqual([n.path for n in notes], ["Projects/approved.md"])
        self.assertIn("No textual evidence", render_vault_job_review("- AWS", notes, "job"))

    def test_excludes_plans_checkboxes_negations_and_code(self):
        self.write(
            "Projects/demo.md",
            "# Demo\n## Próximos passos\n- Kubernetes\n### Future\n- AWS\n"
            "## O que implementei\n- [ ] Experimentar Prometheus\n"
            "Não tenho experiência em Azure.\nQuero aprender GCP.\n"
            "```python\n# Docker\n```\n"
            "Implementei uma pipeline com GitHub Actions.\n",
        )
        notes = read_vault(self.root)
        lines = [line.text for line in notes[0].evidence]
        self.assertEqual(lines, ["Implementei uma pipeline com GitHub Actions."])
        report = render_vault_job_review("- GitHub Actions e Kubernetes", notes, "vaga")
        self.assertIn("Without a detected mention: Kubernetes", report)

    def test_safe_frontmatter_rejects_invalid_yaml(self):
        self.write("Career/bad.md", "---\ntags: [broken\n---\nPython")
        with self.assertRaisesRegex(ValueError, "invalid YAML"):
            read_vault(self.root)

    def test_frontmatter_must_be_map(self):
        self.write("Career/bad.md", "---\n- list\n- not map\n---\nPython")
        with self.assertRaisesRegex(ValueError, "mapping"):
            read_vault(self.root)

    def test_missing_yaml_closer_rejected(self):
        self.write("Career/bad.md", "---\nstatus: active\nPython")
        with self.assertRaisesRegex(ValueError, "closing"):
            read_vault(self.root)

    def test_ignores_symlinked_file_even_if_in_folder(self):
        secret = self.write("00-Inbox/secret.md", "AWS")
        (self.root / "Projects" / "linked.md").symlink_to(secret)
        self.assertEqual(read_vault(self.root), ())

    def test_ignores_symlinked_folder(self):
        (self.root / "Projects" / "linked").symlink_to(
            self.root / "00-Inbox", target_is_directory=True
        )
        self.assertEqual(read_vault(self.root), ())

    def test_bad_path_fails_without_creating_vault(self):
        wrong = self.root / "absent"
        with self.assertRaisesRegex(ValueError, "existing directory"):
            read_vault(wrong)
        self.assertFalse(wrong.exists())

    def test_renders_untrusted_markdown_as_inert_text(self):
        self.write("Projects/demo.md", "Python <script>alert(1)</script> [info] | test")
        report = render_vault_job_review("- Python <img src=x>", read_vault(self.root), "<job>")
        self.assertIn("&lt;img src=x&gt;", report)
        self.assertIn("&lt;script&gt;", report)
        self.assertIn(r"\[info\] \| test", report)
        self.assertNotIn("<script>", report)

    def test_no_notes_gives_nonmisleading_review(self):
        review = render_vault_job_review("- Docker", (), "job")
        self.assertIn("Markdown notes scanned:** 0", review)
        self.assertIn("No textual evidence", review)

    def test_optional_profile_combines_sources(self):
        self.write("Projects/infra.md", "Provisioned AWS network")
        report = render_vault_job_review(
            "- AWS and Docker",
            read_vault(self.root),
            "job",
            profile="Used Docker",
            profile_name="cv.md",
        )
        self.assertIn("Projects/infra.md:L1", report)
        self.assertIn("cv.md:L1", report)
        self.assertIn("All terms mentioned", report)

    def test_empty_job_and_profile_rejected(self):
        with self.assertRaisesRegex(ValueError, "job description"):
            render_vault_job_review(" ", (), "job")
        with self.assertRaisesRegex(ValueError, "profile must not be empty"):
            render_vault_job_review("- AWS", (), "job", profile=" ")


class VaultCliTests(unittest.TestCase):
    def test_cli_reads_vault_without_creating_tasks(self):
        from opencareerops.cli import main

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            (vault / "Projects").mkdir(parents=True)
            note = vault / "Projects" / "demo.md"
            note.write_text("Published a Docker image", encoding="utf-8")
            job = root / "job.txt"
            job.write_text("- Docker", encoding="utf-8")
            output = root / "results" / "job_review.md"
            original = note.read_bytes()
            code = main(
                ["job-review", "--job", str(job), "--vault", str(vault), "--output", str(output)]
            )
            self.assertEqual(code, 0)
            self.assertEqual(note.read_bytes(), original)
            self.assertIn("Projects/demo.md:L1", output.read_text(encoding="utf-8"))
            self.assertFalse((root / "state").exists())

    def test_cli_cannot_write_report_inside_vault(self):
        from opencareerops.cli import main

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Projects").mkdir()
            (root / "Projects" / "project.md").write_text("Docker", encoding="utf-8")
            job = root / "job.txt"
            job.write_text("- Docker", encoding="utf-8")
            target = root / "Projects" / "report.md"
            code = main(
                ["job-review", "--job", str(job), "--vault", str(root), "--output", str(target)]
            )
            self.assertEqual(code, 2)
            self.assertFalse(target.exists())

    def test_cli_needs_at_least_one_source(self):
        from opencareerops.cli import main

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = root / "job.txt"
            job.write_text("- AWS", encoding="utf-8")
            output = root / "review.md"
            self.assertEqual(main(["job-review", "--job", str(job), "--output", str(output)]), 2)
            self.assertFalse(output.exists())
