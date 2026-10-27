"""Curation contracts: compact, attributed, conservative, unapproved."""

import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from opencareerops.curation import curate_project, render_curated_proposal
from opencareerops.knowledge import KnowledgeProposal, SourceMention, inspect_git_project
from opencareerops.vault import read_vault


def mentioned(term: str, path: str, line: int, excerpt: str, kind: str = "config") -> SourceMention:
    return SourceMention(term, path, line, excerpt, kind)


class EvidenceCurationTests(unittest.TestCase):
    def proposal(self, *, mentions=(), observations=(), remote="https://github.com/demo/project"):
        return KnowledgeProposal("my-project", "a" * 40, remote, 4, mentions, observations)

    def test_evidence_grouping_and_commit_pinned_links(self):
        proposal = self.proposal(
            mentions=(
                mentioned("AWS", "infra/main.tf", 4, 'resource "aws_instance" "app" {'),
                mentioned("IaC (.tf)", "infra/main.tf", 4, 'resource "aws_instance" "app" {'),
                mentioned("GitHub Actions (workflow)", ".github/workflows/ci.yml", 5, "jobs:"),
                mentioned("Docker Compose (configuration)", "infra/compose.yml", 2, "services:"),
            ),
            observations=(
                mentioned(
                    "Documented result",
                    "docs/evidence/ec2.md",
                    2,
                    "Environment: Local emulator",
                    "outcome",
                ),
                mentioned(
                    "Documented result",
                    "docs/evidence/ec2.md",
                    7,
                    "Instance provisioned using OpenTofu",
                    "outcome",
                ),
                mentioned(
                    "Documented result",
                    "docs/evidence/release.md",
                    8,
                    "Functional smoke: failed",
                    "outcome",
                ),
                mentioned(
                    "Documented result",
                    "docs/evidence/release.md",
                    9,
                    "Automatic rollback: successful",
                    "outcome",
                ),
                mentioned(
                    "Documented result",
                    "docs/evidence/ec2.md",
                    11,
                    "Cloud parity not claimed",
                    "outcome",
                ),
            ),
        )
        curated = curate_project(proposal)
        self.assertLessEqual(len(curated), 5)
        self.assertEqual(len(curated), 5)
        text = render_curated_proposal(proposal)
        self.assertIn("Infraestrutura declarada", text)
        self.assertIn("rollback", text.lower())
        self.assertIn("Pipeline de CI versionado", text)
        self.assertIn("Cloud parity not claimed", text)
        self.assertIn("Environment: Local emulator", text)
        self.assertIn(f"/blob/{'a' * 40}/docs/evidence/release.md#L9", text)
        self.assertIn("career_evidence: false", text)
        self.assertNotIn("career_evidence: true", text)
        self.assertEqual(text, render_curated_proposal(proposal))

    def test_blank_projects_have_no_fake_achievements(self):
        text = render_curated_proposal(self.proposal())
        self.assertIn("Nenhuma evidência suficiente", text)
        self.assertIn("não confirmado automaticamente", text)
        self.assertNotIn("### 1.", text)

    def test_fallback_does_not_assert_expertise(self):
        text = render_curated_proposal(
            self.proposal(
                mentions=(mentioned("Python", "README.md", 3, "Mentioned Python", "document"),)
            )
        )
        self.assertIn("Tecnologias mencionadas", text)
        self.assertIn("não foram verificados", text)
        self.assertNotIn("domínio em Python", text)

    def test_curated_links_are_escaped_and_no_forged_url(self):
        text = render_curated_proposal(
            self.proposal(
                remote=None,
                mentions=(
                    mentioned("Python", "README.md", 3, "Python <script> [x] | hi", "document"),
                ),
            )
        )
        self.assertIn("`README.md:L3`", text)
        self.assertNotIn("https://github.com/", text)
        self.assertIn("&lt;script&gt;", text)
        self.assertIn(r"\[x\] \| hi", text)

    def test_strict_source_cap_and_non_approved_vault_reader(self):
        candidates = tuple(
            mentioned("AWS", f"infra/{n}.tf", 1, 'resource "aws_vpc" "x" {') for n in range(20)
        )
        proposal = self.proposal(mentions=candidates)
        report = render_curated_proposal(proposal)
        self.assertEqual(report.count("/blob/"), 2)
        with tempfile.TemporaryDirectory() as root:
            vault = Path(root)
            (vault / "Projects").mkdir()
            (vault / "Projects" / "draft.md").write_text(report, encoding="utf-8")
            self.assertEqual(read_vault(vault), ())

    def test_inspector_retains_late_evidence_for_curation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(
                ["git", "-C", str(root), "config", "user.email", "test@example.org"],
                check=True,
            )
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            source = root / "docs" / "evidence"
            source.mkdir(parents=True)
            (source / "01.md").write_text(
                "\n".join([f"- Health check: passed {i}" for i in range(30)]),
                encoding="utf-8",
            )
            (source / "02.md").write_text(
                "Environment: Local emulator\n- Functional smoke: failed\n"
                "- Automatic rollback: successful\n- Cloud parity not claimed\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixtures"], check=True)
            proposal = inspect_git_project(root)
            self.assertGreater(len(proposal.observations), 14)
            self.assertIn("Automatic rollback: successful", render_curated_proposal(proposal))

    def test_cli_curated_switch_is_opt_in(self):
        from opencareerops.cli import main

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            for key, value in (("user.email", "test@example.org"), ("user.name", "Test")):
                subprocess.run(["git", "-C", str(repo), "config", key, value], check=True)
            (repo / "README.md").write_text("Implemented Python in a demo", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True)
            path = root / "curated.md"
            self.assertEqual(
                main(
                    ["knowledge-propose", "--repo", str(repo), "--curated", "--output", str(path)]
                ),
                0,
            )
            self.assertIn("## Realizações candidatas", path.read_text(encoding="utf-8"))
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["knowledge-propose", "--repo", str(repo)]), 0)
            self.assertIn("## Evidências candidatas", output.getvalue())


if __name__ == "__main__":
    unittest.main()
