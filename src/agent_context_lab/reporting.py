"""Report renderers for agent-context-lab."""

from __future__ import annotations

import json
from dataclasses import asdict

from .model import ScanReport


def report_to_dict(report: ScanReport) -> dict[str, object]:
    return {
        "root": str(report.root),
        "score": report.score,
        "findings": [asdict(finding) for finding in report.findings],
        "context_files": [asdict(item) for item in report.context_files],
        "mcp_servers": [asdict(item) for item in report.mcp_servers],
        "stats": report.stats,
    }


def render_json(report: ScanReport) -> str:
    return json.dumps(report_to_dict(report), indent=2, sort_keys=True)


def render_score_json(report: ScanReport) -> str:
    payload = {
        "root": str(report.root),
        "score": report.score,
        "findings": report.stats.get("findings", 0),
        "context_files": report.stats.get("context_files", 0),
        "mcp_servers": report.stats.get("mcp_servers", 0),
        "stats": report.stats,
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def render_context_map_json(report: ScanReport) -> str:
    payload = {
        "root": str(report.root),
        "context_files": [asdict(item) for item in report.context_files],
        "stats": {
            "context_files": report.stats.get("context_files", 0),
            "total_context_chars": report.stats.get("total_context_chars", 0),
            "budget_chars": report.stats.get("budget_chars", 0),
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def render_mcp_json(report: ScanReport) -> str:
    payload = {
        "root": str(report.root),
        "mcp_servers": [asdict(item) for item in report.mcp_servers],
        "stats": {
            "mcp_servers": report.stats.get("mcp_servers", 0),
            "high_risk_mcp_servers": report.stats.get("high_risk_mcp_servers", 0),
            "mcp_configs": report.stats.get("mcp_configs", 0),
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def render_brief_json(report: ScanReport, max_chars: int = 4000) -> str:
    payload = {
        "root": str(report.root),
        "score": report.score,
        "brief": render_brief(report, max_chars=max_chars),
        "stats": report.stats,
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def table_row(values: list[object]) -> str:
    safe = [str(value).replace("|", "\\|").replace("\n", " ") for value in values]
    return "| " + " | ".join(safe) + " |"


def render_findings(report: ScanReport) -> list[str]:
    lines = ["## Findings", ""]
    if not report.findings:
        return lines + ["No findings.", ""]
    lines.extend(
        [
            "| Severity | Rule | Location | Message | Suggestion |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for finding in report.findings:
        location = finding.file if finding.line is None else f"{finding.file}:{finding.line}"
        lines.append(table_row([finding.severity, finding.rule_id, location, finding.message, finding.suggestion]))
    lines.append("")
    return lines


def render_context_map(report: ScanReport) -> str:
    lines = [
        "# Agent Context Map",
        "",
        f"- Root: `{report.root}`",
        f"- Context candidates: {report.stats.get('context_files', 0)}",
        f"- Total context chars: {report.stats.get('total_context_chars', 0)}",
        "",
    ]
    if not report.context_files:
        lines.append("No context files found.")
        return "\n".join(lines).rstrip() + "\n"
    lines.extend(["| Priority | Kind | Chars | Path |", "| ---: | --- | ---: | --- |"])
    for item in report.context_files:
        lines.append(table_row([item.priority, item.kind, item.chars, item.path]))
    return "\n".join(lines).rstrip() + "\n"


def render_mcp(report: ScanReport) -> str:
    lines = [
        "# MCP Risk Report",
        "",
        f"- Root: `{report.root}`",
        f"- MCP servers: {report.stats.get('mcp_servers', 0)}",
        f"- High-risk servers: {report.stats.get('high_risk_mcp_servers', 0)}",
        "",
    ]
    if not report.mcp_servers:
        lines.append("No MCP servers found.")
        return "\n".join(lines).rstrip() + "\n"
    lines.extend(["| Risk | Server | Command | Reasons | File |", "| --- | --- | --- | --- | --- |"])
    for server in report.mcp_servers:
        lines.append(table_row([server.risk, server.name, server.command, ", ".join(server.reasons) or "-", server.file]))
    return "\n".join(lines).rstrip() + "\n"


def render_score(report: ScanReport) -> str:
    return "\n".join(
        [
            f"score: {report.score}",
            f"findings: {report.stats.get('findings', 0)}",
            f"context_files: {report.stats.get('context_files', 0)}",
            f"mcp_servers: {report.stats.get('mcp_servers', 0)}",
        ]
    ) + "\n"


def render_brief(report: ScanReport, max_chars: int = 4000) -> str:
    lines = [
        "# Agent Context Brief",
        "",
        f"Score: {report.score}/100",
        f"Root: `{report.root}`",
        "",
        "## What The Agent Will See First",
        "",
    ]
    for item in report.context_files[:8]:
        lines.append(f"- `{item.path}` ({item.kind}, {item.chars} chars, priority {item.priority})")
    if not report.context_files:
        lines.append("- No obvious agent context files were found.")

    lines.extend(["", "## Fix First", ""])
    for finding in report.findings[:6]:
        location = finding.file if finding.line is None else f"{finding.file}:{finding.line}"
        lines.append(f"- [{finding.severity}] {finding.rule_id} at `{location}`: {finding.message}")
    if not report.findings:
        lines.append("- No immediate blockers found.")

    if report.mcp_servers:
        lines.extend(["", "## MCP Tools", ""])
        for server in report.mcp_servers:
            lines.append(f"- `{server.name}` risk={server.risk}: {', '.join(server.reasons) or 'no obvious risk markers'}")

    text = "\n".join(lines).rstrip() + "\n"
    if len(text) <= max_chars:
        return text
    suffix = "\n\n[brief truncated to max chars]\n"
    return text[: max(0, max_chars - len(suffix))].rstrip() + suffix


def render_markdown(report: ScanReport) -> str:
    lines = [
        "# Agent Context Lab Report",
        "",
        f"- Root: `{report.root}`",
        f"- Score: {report.score}/100",
        f"- Findings: {report.stats.get('findings', 0)}",
        f"- Context files: {report.stats.get('context_files', 0)}",
        f"- MCP servers: {report.stats.get('mcp_servers', 0)}",
        "",
    ]
    lines.extend(render_findings(report))
    lines.append(render_context_map(report).rstrip())
    lines.append("")
    lines.append(render_mcp(report).rstrip())
    return "\n".join(lines).rstrip() + "\n"
