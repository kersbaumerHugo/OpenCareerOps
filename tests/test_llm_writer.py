"""Offline LLM writer tests: explicit consent, strict refs, safe failures and compatibility."""

import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from opencareerops.cli import main
from opencareerops.knowledge import KnowledgeProposal, SourceMention
from opencareerops.llm_writer import (
    _endpoint,
    _post_json,
    build_evidence_packet,
    generate_llm_proposal,
    parse_model_draft,
    render_llm_proposal,
)


def mention(path: str, line: int, excerpt: str, kind: str = "outcome") -> SourceMention:
    return SourceMention("Documented result", path, line, excerpt, kind)


def proposal() -> KnowledgeProposal:
    return KnowledgeProposal(
        "demo-cloud-lab",
        "a" * 40,
        "https://github.com/example/demo-cloud-lab",
        8,
        (
            mention("infra/main.tf", 1, 'resource "aws_instance" "demo" {', "config"),
            mention(".github/workflows/ci.yml", 4, "jobs:", "config"),
            mention("infra/compose.yaml", 1, "services:", "config"),
        ),
        (
            mention("docs/evidence/smoke.md", 2, "Environment: local Floci emulator"),
            mention("docs/evidence/smoke.md", 4, "Instance provisioned using OpenTofu"),
            mention("docs/evidence/smoke.md", 9, "Automatic rollback: successful"),
            mention("docs/evidence/smoke.md", 11, "Cloud parity: not demonstrated"),
        ),
    )


def response_for(packet):
    infra = next(i for i, v in packet.sources.items() if "resource" in v.excerpt)
    rollback = next(i for i, v in packet.sources.items() if "rollback" in v.excerpt.lower())
    limit = next(i for i, v in packet.sources.items() if "not demonstrated" in v.excerpt)
    return {
        "claims": [
            {
                "text": (
                    "O repositório contém definições versionadas de infraestrutura AWS simulada."
                ),
                "evidence_ids": [infra],
            },
            {
                "text": "O laboratório registra um experimento de rollback automatizado.",
                "evidence_ids": [rollback],
            },
        ],
        "limitations": [
            {
                "text": "Os registros não demonstram paridade completa com a nuvem real.",
                "evidence_ids": [limit],
            }
        ],
    }


class LLMEvidenceWriterTests(unittest.TestCase):
    def setUp(self):
        self.proposal = proposal()
        self.packet = build_evidence_packet(self.proposal)

    def valid(self):
        return json.dumps(response_for(self.packet), ensure_ascii=False)

    def test_packet_is_bounded_and_contains_selected_evidence_only(self):
        self.assertIn("candidate_groups", self.packet.data)
        self.assertLessEqual(len(self.packet.sources), 20)
        self.assertTrue(all(i.startswith("E") for i in self.packet.sources))
        self.assertNotIn("password", json.dumps(self.packet.data).lower())
        self.assertIn("local Floci emulator", json.dumps(self.packet.data))

    def test_valid_draft_is_source_linked_and_not_approved(self):
        draft = parse_model_draft(self.valid(), self.packet)
        output = render_llm_proposal(self.proposal, self.packet, draft, "local-model")
        self.assertIn("career_evidence: false", output)
        self.assertIn("status: proposed", output)
        self.assertIn("writer: llm", output)
        self.assertIn("#L1", output)
        self.assertIn("#L9", output)
        self.assertIn("Cloud parity: not demonstrated", output)
        self.assertIn("Environment: local Floci emulator", output)
        self.assertNotIn("career_evidence: true", output)
        self.assertNotIn("Fonte E999", output)

    def test_unknown_reference_is_rejected(self):
        raw = response_for(self.packet)
        raw["claims"][0]["evidence_ids"] = ["E999"]
        with self.assertRaisesRegex(ValueError, "unknown or duplicate"):
            parse_model_draft(json.dumps(raw), self.packet)

    def test_duplicate_reference_is_rejected(self):
        raw = response_for(self.packet)
        evidence_id = raw["claims"][0]["evidence_ids"][0]
        raw["claims"][0]["evidence_ids"] = [evidence_id, evidence_id]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            parse_model_draft(json.dumps(raw), self.packet)

    def test_unsupported_numeric_claim_is_rejected(self):
        raw = response_for(self.packet)
        raw["claims"][0]["text"] = "O projeto gerou 99% de melhoria de confiabilidade no serviço."
        with self.assertRaisesRegex(ValueError, "number absent"):
            parse_model_draft(json.dumps(raw), self.packet)

    def test_personal_authorship_claim_is_rejected(self):
        raw = response_for(self.packet)
        raw["claims"][0]["text"] = "Eu desenvolvi um sistema de produção com AWS e Terraform."
        with self.assertRaisesRegex(ValueError, "authorship"):
            parse_model_draft(json.dumps(raw), self.packet)

    def test_invalid_schema_and_empty_claims_fail_closed(self):
        variants = (
            "```json\n{}\n```",
            "{}",
            '{"claims": [], "limitations": []}',
            '{"claims": "fake", "limitations": []}',
            '{"claims": [{}], "limitations": []}',
        )
        for value in variants:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_model_draft(value, self.packet)

    def test_html_from_model_is_escaped(self):
        raw = response_for(self.packet)
        raw["claims"][0]["text"] = (
            "O repositório inclui <script>alert('x')</script> em configuração versionada."
        )
        draft = parse_model_draft(json.dumps(raw), self.packet)
        text = render_llm_proposal(self.proposal, self.packet, draft, "test-model")
        self.assertNotIn("<script>", text)
        self.assertIn("&lt;script&gt;", text)

    def test_model_failure_does_not_silently_fallback(self):
        with patch("opencareerops.llm_writer._post_json", return_value={"choices": []}):
            with self.assertRaisesRegex(ValueError, "no assistant content"):
                generate_llm_proposal(
                    self.proposal,
                    base_url="http://127.0.0.1:8000/v1",
                    model="test",
                )

    def test_successful_mocked_generation_requires_no_network(self):
        with patch("opencareerops.llm_writer._post_json") as mock:
            mock.return_value = {"choices": [{"message": {"content": self.valid()}}]}
            text = generate_llm_proposal(
                self.proposal, base_url="http://127.0.0.1:8000/v1", model="local"
            )
            self.assertIn("rollback", text.lower())
            self.assertEqual(mock.call_count, 1)
            self.assertEqual(mock.call_args.args[0], "http://127.0.0.1:8000/v1/chat/completions")
            self.assertEqual(mock.call_args.args[1]["model"], "local")

    def test_remote_requires_explicit_opt_in(self):
        with self.assertRaisesRegex(ValueError, "explicit"):
            _endpoint("https://api.example.org/v1", allow_remote=False)
        self.assertEqual(
            _endpoint("https://api.example.org/v1", allow_remote=True),
            "https://api.example.org/v1/chat/completions",
        )

    def test_insecure_remote_and_credentials_rejected(self):
        urls = (
            "http://api.example.org/v1",
            "https://token@api.example.org/v1",
            "https://api.example.org/v1?secret=123",
            "https://api.example.org/v1#frag",
            "file:///etc/passwd",
            "https://api.example.org:0/v1",
            "https://api.example.org/v1/chat/completions",
        )
        for url in urls:
            with self.subTest(url=url), self.assertRaises(ValueError):
                _endpoint(url, allow_remote=True)

    def test_localhost_endpoints_do_not_require_remote_opt_in(self):
        self.assertIn(
            "/chat/completions", _endpoint("http://localhost:1234/v1", allow_remote=False)
        )
        self.assertIn("/chat/completions", _endpoint("http://[::1]:8000/v1", allow_remote=False))
        with self.assertRaises(ValueError):
            _endpoint("http://127.0.0.2:8000/v1", allow_remote=False)

    def test_no_evidence_does_not_call_model(self):
        empty = KnowledgeProposal("empty", "b" * 40, None, 0, (), ())
        with patch("opencareerops.llm_writer._post_json") as mock:
            with self.assertRaisesRegex(ValueError, "no curated evidence"):
                generate_llm_proposal(empty, base_url="http://localhost:8000/v1", model="test")
            mock.assert_not_called()

    def test_http_transport_honors_response_size_and_secrets(self):
        class Response:
            def __init__(self, data):
                self.data = data

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self, maximum):
                return self.data[:maximum]

        class Opener:
            def __init__(self, content):
                self.content = content
                self.request = None

            def open(self, request, timeout):
                self.request = request
                self.timeout = timeout
                return Response(self.content)

        opener = Opener(b'{"choices": []}')
        with patch("opencareerops.llm_writer.build_opener", return_value=opener):
            self.assertEqual(
                _post_json("http://localhost/v1", {"model": "x"}, "test-key"), {"choices": []}
            )
        self.assertIn("Bearer test-key", opener.request.get_header("Authorization"))
        self.assertEqual(opener.timeout, 30)
        opener = Opener(b"a" * (64 * 1024 + 1))
        with patch("opencareerops.llm_writer.build_opener", return_value=opener):
            with self.assertRaisesRegex(ValueError, "64 KiB"):
                _post_json("http://localhost/v1", {}, None)


class LLMCliTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.repo = self.root / "demo-project"
        self.repo.mkdir()
        for command in (
            ("init", "-q"),
            ("config", "user.email", "ci@example.org"),
            ("config", "user.name", "CI"),
        ):
            subprocess.run(["git", "-C", str(self.repo), *command], check=True, capture_output=True)
        (self.repo / "infra").mkdir()
        (self.repo / "infra" / "main.tf").write_text(
            'resource "aws_instance" "app" {}\n', encoding="utf-8"
        )
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "snapshot"], check=True)
        self.vault = self.root / "vault"
        (self.vault / "Projects").mkdir(parents=True)
        self.output = self.root / "out" / "draft.md"

    def invoke(self, *extra):
        args = [
            "knowledge-propose",
            "--repo",
            str(self.repo),
            "--vault",
            str(self.vault),
            "--output",
            str(self.output),
            *extra,
        ]
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = main(args)
        return code, stderr.getvalue()

    def test_llm_mode_writes_unapproved_note_only_outside_vault(self):
        from opencareerops.knowledge import inspect_git_project
        from opencareerops.llm_writer import build_evidence_packet

        packet = build_evidence_packet(inspect_git_project(self.repo))
        identifier = next(iter(packet.sources))
        valid = {
            "claims": [
                {
                    "text": "O repositório contém uma definição de recurso AWS versionada.",
                    "evidence_ids": [identifier],
                }
            ],
            "limitations": [],
        }
        with patch("opencareerops.llm_writer._post_json") as mock:
            mock.return_value = {"choices": [{"message": {"content": json.dumps(valid)}}]}
            code, error = self.invoke(
                "--writer",
                "llm",
                "--llm-base-url",
                "http://localhost:8000/v1",
                "--llm-model",
                "test",
            )
        self.assertEqual(code, 0, error)
        self.assertIn("career_evidence: false", self.output.read_text(encoding="utf-8"))
        self.assertEqual(list((self.vault / "Projects").iterdir()), [])

    def test_failed_model_response_never_creates_output(self):
        with patch("opencareerops.llm_writer._post_json", return_value={"choices": []}):
            code, error = self.invoke(
                "--writer",
                "llm",
                "--llm-base-url",
                "http://localhost:8000/v1",
                "--llm-model",
                "test",
            )
        self.assertEqual(code, 2)
        self.assertIn("assistant content", error)
        self.assertFalse(self.output.exists())

    def test_cli_requires_remote_opt_in_and_https(self):
        code, error = self.invoke(
            "--writer",
            "llm",
            "--llm-base-url",
            "https://provider.example/v1",
            "--llm-model",
            "test",
        )
        self.assertEqual(code, 2)
        self.assertIn("--allow-remote-llm", error)
        self.assertFalse(self.output.exists())

    def test_cli_missing_llm_settings_fails(self):
        with patch.dict("os.environ", {}, clear=True):
            code, error = self.invoke("--writer", "llm")
        self.assertEqual(code, 2)
        self.assertIn("--llm-base-url", error)
        self.assertFalse(self.output.exists())

    def test_legacy_curated_mode_still_works_without_network(self):
        with patch("opencareerops.llm_writer._post_json") as mock:
            code, error = self.invoke("--curated")
        self.assertEqual(code, 0, error)
        self.assertIn("síntese candidata", self.output.read_text(encoding="utf-8"))
        mock.assert_not_called()

    def test_llm_flags_cannot_be_ignored_in_deterministic_mode(self):
        code, error = self.invoke("--allow-remote-llm")
        self.assertEqual(code, 2)
        self.assertIn("require --writer llm", error)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
