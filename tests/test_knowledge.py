"""Offline, committed-only, read-only knowledge proposal tests."""

import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from opencareerops.cli import main
from opencareerops.knowledge import (
    _canonical_github_remote,
    inspect_git_project,
    render_knowledge_proposal,
)
from opencareerops.vault import read_vault


def run_git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


class KnowledgeProposalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "fictional-infra"
        self.repo.mkdir()
        run_git(self.repo, "init", "-q")
        run_git(self.repo, "config", "user.name", "Fictional Person")
        run_git(self.repo, "config", "user.email", "fictional@example.org")
        run_git(
            self.repo,
            "remote",
            "add",
            "origin",
            "https://github.com/example/fictional-infra.git",
        )

    def file(self, relative: str, content: str) -> Path:
        path = self.repo / relative
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_text(content, encoding="utf-8")
        return path

    def commit(self):
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-qm", "snapshot")

    def test_committed_proposal_and_sources(self):
        self.file(
            "README.md",
            "# Demo\nImplemented Python and Docker automation.\n## Next steps\n- Kubernetes\n",
        )
        self.file(
            "docs/evidence/smoke.md",
            "# Smoke\nEnvironment: Local emulator\n"
            "- Docker health check: passed\n- Automatic rollback: successful\n"
            "- Cloud parity: not demonstrated\n",
        )
        self.file("infra/main.tf", 'resource "aws_instance" "demo" {\n  count = 1\n}\n')
        self.file(".github/workflows/ci.yml", "jobs:\n  tests:\n    runs-on: ubuntu-latest\n")
        self.commit()
        proposal = inspect_git_project(self.repo)
        text = render_knowledge_proposal(proposal)
        self.assertEqual(proposal.name, "fictional-infra")
        self.assertEqual(proposal.sources_scanned, 4)
        self.assertEqual(len(proposal.revision), 40)
        self.assertEqual(proposal.repository_url, "https://github.com/example/fictional-infra")
        self.assertIn("Docker", text)
        self.assertIn("AWS", text)
        self.assertIn("IaC (.tf)", text)
        self.assertIn("GitHub Actions (workflow)", text)
        self.assertIn("docs/evidence/smoke.md:L3", text)
        self.assertIn("## Registros documentados de validação e limitações", text)
        self.assertIn("Environment: Local emulator", text)
        self.assertIn("Automatic rollback: successful", text)
        self.assertIn("Cloud parity: not demonstrated", text)
        self.assertIn(f"/blob/{proposal.revision}/infra/main.tf#L1", text)
        self.assertNotIn("### Kubernetes", text)
        self.assertIn("career_evidence: false", text)
        self.assertIn("source_commit:", text)
        self.assertIn("não comprovam autoria", text)
        self.assertEqual(text, render_knowledge_proposal(proposal))

    def test_uncommitted_changes_and_untracked_secrets_not_read(self):
        original = self.file("README.md", "Documented Python services.\n")
        self.commit()
        original.write_text("Documented Kubernetes services.\n", encoding="utf-8")
        self.file("README-untracked.md", "Secret: fake\nUsed Terraform\n")
        proposal = inspect_git_project(self.repo)
        self.assertEqual({x.term for x in proposal.mentions}, {"Python"})
        self.assertEqual(proposal.sources_scanned, 1)

    def test_skips_symlink_and_sensitive_text(self):
        self.file("README.md", "Python API_KEY=SUPER_SECRET\nUsed AWS in a safe lab.\n")
        self.file(".env", "PASSWORD=secret")
        self.file("docs/evidence/api-token.md", "Docker")
        (self.repo / "readme-link.md").symlink_to("README.md")
        self.commit()
        proposal = inspect_git_project(self.repo)
        self.assertEqual([x.term for x in proposal.mentions], ["AWS"])
        self.assertNotIn("SUPER_SECRET", render_knowledge_proposal(proposal))
        self.assertEqual(proposal.sources_scanned, 1)

    def test_remotes_are_strictly_allowlisted(self):
        self.assertEqual(
            _canonical_github_remote("git@github.com:acme/repo.git"),
            "https://github.com/acme/repo",
        )
        for url in (
            "https://github.com/owner/repo?token=private",
            "https://evil.example/owner/repo",
            "https://myname:token@github.com/owner/repo",
            "file:///tmp/local",
        ):
            with self.subTest(url=url):
                self.assertIsNone(_canonical_github_remote(url))

    def test_no_origin_does_not_create_fake_github_url(self):
        self.file("README.md", "Used Docker")
        self.commit()
        run_git(self.repo, "remote", "remove", "origin")
        draft = render_knowledge_proposal(inspect_git_project(self.repo))
        self.assertIn("local-git-checkout", draft)
        self.assertIn("`README.md:L1`", draft)
        self.assertNotIn("https://github.com/", draft)

    def test_vault_ignores_proposed_note_until_approval(self):
        self.file("README.md", "Wrote Python tests")
        self.commit()
        draft = render_knowledge_proposal(inspect_git_project(self.repo))
        vault = self.root / "vault"
        (vault / "Projects").mkdir(parents=True)
        note = vault / "Projects" / "demo.md"
        note.write_text(draft, encoding="utf-8")
        self.assertEqual(read_vault(vault), ())

    def test_subfolder_rejected(self):
        self.file("infra/main.tf", 'resource "aws_vpc" "demo" {}')
        self.commit()
        with self.assertRaisesRegex(ValueError, "Git repository root"):
            inspect_git_project(self.repo / "infra")

    def test_no_repository_rejected(self):
        with self.assertRaisesRegex(ValueError, "existing directory"):
            inspect_git_project(self.root / "absent")
        with self.assertRaisesRegex(ValueError, "valid local Git checkout"):
            inspect_git_project(self.root)

    def test_skips_large_source_and_invalid_utf8(self):
        self.file("README.md", "x" * (256 * 1024 + 1))
        (self.repo / "docs" / "evidence").mkdir(parents=True)
        (self.repo / "docs" / "evidence" / "broken.md").write_bytes(b"\xff\xfe")
        self.commit()
        proposal = inspect_git_project(self.repo)
        self.assertEqual(proposal.sources_scanned, 0)
        self.assertEqual(proposal.mentions, ())
        self.assertIn("Nenhuma menção reconhecida", render_knowledge_proposal(proposal))

    def test_cli_generates_outside_repo_and_never_changes_vault(self):
        self.file("README.md", "Built Python service")
        self.commit()
        vault = self.root / "vault"
        (vault / "Projects").mkdir(parents=True)
        output = self.root / "out" / "proposal.md"
        code = main(
            [
                "knowledge-propose",
                "--repo",
                str(self.repo),
                "--vault",
                str(vault),
                "--output",
                str(output),
            ]
        )
        self.assertEqual(code, 0)
        self.assertIn("status: proposed", output.read_text(encoding="utf-8"))
        self.assertEqual(list((vault / "Projects").iterdir()), [])
        self.assertFalse((self.repo / "Projects").exists())

    def test_cli_blocks_writes_within_source_or_vault(self):
        self.file("README.md", "Python")
        self.commit()
        vault = self.root / "vault"
        (vault / "Projects").mkdir(parents=True)
        for output in (self.repo / "output" / "draft.md", vault / "Projects" / "draft.md"):
            with self.subTest(output=output):
                stderr = io.StringIO()
                with redirect_stderr(stderr):
                    code = main(
                        [
                            "knowledge-propose",
                            "--repo",
                            str(self.repo),
                            "--vault",
                            str(vault),
                            "--output",
                            str(output),
                        ]
                    )
                self.assertEqual(code, 2)
                self.assertIn("outside", stderr.getvalue())
                self.assertFalse(output.exists())

    def test_cli_stdout_is_read_only(self):
        self.file("README.md", "Documented SQL")
        self.commit()
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = main(["knowledge-propose", "--repo", str(self.repo)])
        self.assertEqual(code, 0)
        self.assertIn("### SQL", stdout.getvalue())

    def test_readme_goals_do_not_turn_into_evidence(self):
        self.file(
            "README.md",
            "# Lab\n## Goals\n- Deploy Kubernetes on AWS\n"
            "## Architecture\n- Run Prometheus\n"
            "## Validated locally\n- Docker health check passed\n",
        )
        self.commit()
        proposal = inspect_git_project(self.repo)
        self.assertEqual({item.term for item in proposal.mentions}, {"Docker"})
        self.assertIn("README.md:L7", render_knowledge_proposal(proposal))

    def test_does_not_treat_markdown_scripts_as_evidence(self):
        self.file("README.md", "# Demo\n```python\nimport fastapi\n```\n## Planned\n- Kubernetes\n")
        self.commit()
        self.assertEqual(inspect_git_project(self.repo).mentions, ())


if __name__ == "__main__":
    unittest.main()
