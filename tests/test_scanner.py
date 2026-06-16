import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_context_lab.scanner import scan_repository


ROOT = Path(__file__).resolve().parents[1]


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class ScannerTests(unittest.TestCase):
    def test_clean_example_scores_100(self):
        report = scan_repository(ROOT / "examples" / "clean-agent-repo")
        self.assertEqual(100, report.score)
        self.assertEqual(1, report.stats["instruction_files"])

    def test_conflicting_example_finds_ask_and_dependency_conflicts(self):
        report = scan_repository(ROOT / "examples" / "conflicting-agent-repo")
        rule_ids = {finding.rule_id for finding in report.findings}
        self.assertIn("ACL-CONFLICT-ASK", rule_ids)
        self.assertIn("ACL-CONFLICT-DEPS", rule_ids)
        self.assertLess(report.score, 80)

    def test_bloated_example_finds_duplicate_context(self):
        report = scan_repository(ROOT / "examples" / "bloated-context-repo")
        self.assertTrue(any(finding.rule_id == "ACL-DUPLICATE-CONTEXT" for finding in report.findings))

    def test_bloated_example_finds_stale_context(self):
        report = scan_repository(ROOT / "examples" / "bloated-context-repo")
        self.assertTrue(any(finding.rule_id == "ACL-STALE-CONTEXT" for finding in report.findings))

    def test_cursor_rules_are_context_files(self):
        report = scan_repository(ROOT / "examples" / "bloated-context-repo")
        paths = {item.path for item in report.context_files}
        self.assertIn(".cursor/rules/legacy.md", paths)

    def test_mcp_risk_example_detects_two_servers(self):
        report = scan_repository(ROOT / "examples" / "mcp-risk-repo")
        self.assertEqual(2, report.stats["mcp_servers"])
        self.assertEqual(2, report.stats["high_risk_mcp_servers"])

    def test_mcp_risk_reasons_include_secret_and_shell(self):
        report = scan_repository(ROOT / "examples" / "mcp-risk-repo")
        shell_runner = next(server for server in report.mcp_servers if server.name == "shell-runner")
        self.assertIn("shell command", shell_runner.reasons)
        self.assertIn("secret-like environment variable", shell_runner.reasons)

    def test_missing_instruction_file_is_a_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "README.md", "# Demo\n")
            report = scan_repository(root)
        self.assertTrue(any(finding.rule_id == "ACL-MISSING-INSTRUCTIONS" for finding in report.findings))

    def test_missing_scan_path_is_a_hard_error_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "missing"
            report = scan_repository(root)
        self.assertEqual(0, report.score)
        self.assertTrue(report.stats["scan_error"])
        self.assertEqual("ACL-MISSING-PATH", report.findings[0].rule_id)

    def test_budget_exceeded_is_a_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "AGENTS.md", "# Agent\n" + "x" * 200)
            report = scan_repository(root, budget_chars=50)
        self.assertTrue(any(finding.rule_id == "ACL-CONTEXT-BUDGET" for finding in report.findings))

    def test_invalid_mcp_json_is_a_high_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "AGENTS.md", "# Agent\n")
            write(root / ".mcp.json", "{bad json")
            report = scan_repository(root)
        finding = next(finding for finding in report.findings if finding.rule_id == "ACL-MCP-JSON")
        self.assertEqual("high", finding.severity)

    def test_non_utf8_context_is_preserved_with_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_bytes(b"# Agent\nvalid\xfftext\n")
            report = scan_repository(root)
        self.assertEqual(100, report.score)
        self.assertEqual(1, report.stats["instruction_files"])

    def test_read_error_is_a_deterministic_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "AGENTS.md", "# Agent\n")
            with patch("agent_context_lab.scanner.read_text", side_effect=OSError("denied")):
                report = scan_repository(root)
        self.assertTrue(any(finding.rule_id == "ACL-READ-ERROR" for finding in report.findings))

    def test_unexpected_mcp_shape_is_a_medium_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "AGENTS.md", "# Agent\n")
            write(root / ".mcp.json", '{"mcpServers": []}')
            report = scan_repository(root)
        finding = next(finding for finding in report.findings if finding.rule_id == "ACL-MCP-SHAPE")
        self.assertEqual("medium", finding.severity)

    def test_malformed_mcp_server_entry_is_a_medium_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "AGENTS.md", "# Agent\n")
            write(root / ".mcp.json", '{"mcpServers": {"bad": "not-an-object"}}')
            report = scan_repository(root)
        finding = next(finding for finding in report.findings if finding.rule_id == "ACL-MCP-SERVER-SHAPE")
        self.assertEqual("medium", finding.severity)

    def test_test_guidance_conflict_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "AGENTS.md", "Run tests before completion.\nIgnore test failures during prototypes.\n")
            report = scan_repository(root)
        self.assertTrue(any(finding.rule_id == "ACL-CONFLICT-TESTS" for finding in report.findings))

    def test_context_files_are_priority_sorted(self):
        report = scan_repository(ROOT / "examples" / "bloated-context-repo")
        priorities = [item.priority for item in report.context_files]
        self.assertEqual(sorted(priorities, reverse=True), priorities)

    def test_score_never_goes_below_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = "\n".join(["deprecated legacy todo fixme"] * 30)
            write(root / "AGENTS.md", text)
            write(root / "CLAUDE.md", "Never ask before every edit.\nAlways ask before every edit.\n")
            write(root / ".mcp.json", "{bad json")
            report = scan_repository(root, budget_chars=20)
        self.assertGreaterEqual(report.score, 0)


if __name__ == "__main__":
    unittest.main()
