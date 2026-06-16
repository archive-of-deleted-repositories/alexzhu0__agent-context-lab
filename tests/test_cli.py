import contextlib
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_context_lab.cli import build_parser, main, render_report


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def test_parser_accepts_scan_subcommand(self):
        args = build_parser().parse_args(["scan", str(ROOT / "examples" / "clean-agent-repo")])
        self.assertEqual("scan", args.command)

    def test_render_report_scan_markdown(self):
        score, output, scan_error = render_report("scan", str(ROOT / "examples" / "conflicting-agent-repo"), "markdown", 24000)
        self.assertEqual(55, score)
        self.assertFalse(scan_error)
        self.assertIn("Agent Context Lab Report", output)

    def test_render_report_scan_json(self):
        score, output, scan_error = render_report("scan", str(ROOT / "examples" / "conflicting-agent-repo"), "json", 24000)
        self.assertEqual(55, score)
        self.assertFalse(scan_error)
        self.assertEqual(55, json.loads(output)["score"])

    def test_score_command_outputs_compact_score(self):
        score, output, _ = render_report("score", str(ROOT / "examples" / "conflicting-agent-repo"), "markdown", 24000)
        self.assertEqual(55, score)
        self.assertIn("score: 55", output)

    def test_map_command_outputs_context_map(self):
        _, output, _ = render_report("map", str(ROOT / "examples" / "clean-agent-repo"), "markdown", 24000)
        self.assertIn("Agent Context Map", output)

    def test_mcp_command_outputs_mcp_report(self):
        _, output, _ = render_report("mcp", str(ROOT / "examples" / "mcp-risk-repo"), "markdown", 24000)
        self.assertIn("MCP Risk Report", output)

    def test_brief_command_outputs_brief(self):
        _, output, _ = render_report("brief", str(ROOT / "examples" / "bloated-context-repo"), "markdown", 24000)
        self.assertIn("Agent Context Brief", output)

    def test_score_json_is_command_specific(self):
        _, output, _ = render_report("score", str(ROOT / "examples" / "conflicting-agent-repo"), "json", 24000)
        payload = json.loads(output)
        self.assertEqual(55, payload["score"])
        self.assertIsInstance(payload["findings"], int)
        self.assertIn("stats", payload)

    def test_map_json_is_command_specific(self):
        _, output, _ = render_report("map", str(ROOT / "examples" / "clean-agent-repo"), "json", 24000)
        payload = json.loads(output)
        self.assertIn("context_files", payload)
        self.assertNotIn("findings", payload)

    def test_mcp_json_is_command_specific(self):
        _, output, _ = render_report("mcp", str(ROOT / "examples" / "mcp-risk-repo"), "json", 24000)
        payload = json.loads(output)
        self.assertEqual(2, len(payload["mcp_servers"]))
        self.assertNotIn("context_files", payload)

    def test_brief_json_contains_brief(self):
        _, output, _ = render_report("brief", str(ROOT / "examples" / "bloated-context-repo"), "json", 24000, max_chars=240)
        payload = json.loads(output)
        self.assertIn("Agent Context Brief", payload["brief"])

    def test_brief_render_scans_once(self):
        with patch("agent_context_lab.cli.scan_repository") as scan_repository:
            scan_repository.return_value = __import__("agent_context_lab.scanner", fromlist=["scan_repository"]).scan_repository(
                ROOT / "examples" / "clean-agent-repo"
            )
            render_report("brief", str(ROOT / "examples" / "clean-agent-repo"), "markdown", 24000, max_chars=200)
        self.assertEqual(1, scan_repository.call_count)

    def test_render_report_missing_path_marks_scan_error(self):
        score, output, scan_error = render_report("scan", str(ROOT / "examples" / "missing"), "json", 24000)
        self.assertEqual(0, score)
        self.assertTrue(scan_error)
        self.assertEqual("ACL-MISSING-PATH", json.loads(output)["findings"][0]["rule_id"])

    def test_main_success_returns_zero(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = main(["scan", str(ROOT / "examples" / "clean-agent-repo"), "--fail-under", "90"])
        self.assertEqual(0, exit_code)

    def test_main_fail_under_returns_two(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = main(["scan", str(ROOT / "examples" / "conflicting-agent-repo"), "--fail-under", "80"])
        self.assertEqual(2, exit_code)

    def test_main_brief_respects_max_chars(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = main(["brief", str(ROOT / "examples" / "bloated-context-repo"), "--max-chars", "160"])
        self.assertEqual(0, exit_code)
        self.assertLessEqual(len(buffer.getvalue()), 170)

    def test_main_missing_path_returns_one(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = main(["scan", str(ROOT / "examples" / "missing"), "--fail-under", "1"])
        self.assertEqual(1, exit_code)
        self.assertIn("scan target failed", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
