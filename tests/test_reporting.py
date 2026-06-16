import json
import unittest
from pathlib import Path

from agent_context_lab.reporting import render_brief, render_context_map, render_json, render_markdown, render_mcp, render_score
from agent_context_lab.scanner import scan_repository


ROOT = Path(__file__).resolve().parents[1]


class ReportingTests(unittest.TestCase):
    def test_json_report_is_parseable(self):
        report = scan_repository(ROOT / "examples" / "conflicting-agent-repo")
        payload = json.loads(render_json(report))
        self.assertEqual(report.score, payload["score"])

    def test_markdown_report_has_findings_table(self):
        report = scan_repository(ROOT / "examples" / "conflicting-agent-repo")
        output = render_markdown(report)
        self.assertIn("| Severity | Rule | Location | Message | Suggestion |", output)

    def test_context_map_lists_instruction_file(self):
        report = scan_repository(ROOT / "examples" / "clean-agent-repo")
        output = render_context_map(report)
        self.assertIn("AGENTS.md", output)

    def test_mcp_report_lists_risk_table(self):
        report = scan_repository(ROOT / "examples" / "mcp-risk-repo")
        output = render_mcp(report)
        self.assertIn("shell-runner", output)
        self.assertIn("High-risk servers: 2", output)

    def test_score_report_is_compact(self):
        report = scan_repository(ROOT / "examples" / "conflicting-agent-repo")
        output = render_score(report)
        self.assertIn("score: 55", output)

    def test_brief_truncates_to_max_chars(self):
        report = scan_repository(ROOT / "examples" / "bloated-context-repo")
        output = render_brief(report, max_chars=120)
        self.assertLessEqual(len(output), 120)
        self.assertIn("truncated", output)


if __name__ == "__main__":
    unittest.main()
