"""Repository scanner for coding-agent context readiness."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Iterable

from .model import ContextFile, Finding, McpServer, ScanReport


SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
}

INSTRUCTION_NAMES = {
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    ".cursorrules",
    ".windsurfrules",
    "copilot-instructions.md",
}

MCP_NAMES = {
    ".mcp.json",
    "mcp.json",
    "mcp.servers.json",
}

STALE_RE = re.compile(r"\b(deprecated|outdated|legacy|todo|fixme)\b", re.IGNORECASE)
SECRET_RE = re.compile(r"(TOKEN|SECRET|KEY|PASSWORD|CREDENTIAL)", re.IGNORECASE)
NETWORK_RE = re.compile(r"https?://|curl\s+|wget\s+", re.IGNORECASE)
CONFLICT_RULES = [
    (
        "ACL-CONFLICT-ASK",
        re.compile(r"\b(always\s+ask|ask\s+before)\b", re.IGNORECASE),
        re.compile(r"\b(do\s+not\s+ask|never\s+ask)\b", re.IGNORECASE),
        "Conflicting edit-permission guidance can make agents pause or act without approval unpredictably.",
        "Keep one explicit permission rule for coding agents.",
    ),
    (
        "ACL-CONFLICT-DEPS",
        re.compile(r"\b(never\s+add\s+dependencies|do\s+not\s+add\s+dependencies)\b", re.IGNORECASE),
        re.compile(r"\b(add\s+any\s+dependency|add\s+dependencies)\b", re.IGNORECASE),
        "Dependency policy conflicts make automated changes harder to review.",
        "State when dependencies are allowed and who approves them.",
    ),
    (
        "ACL-CONFLICT-TESTS",
        re.compile(r"\b(run\s+tests|must\s+test|before\s+reporting\s+completion)\b", re.IGNORECASE),
        re.compile(r"\b(ignore\s+test\s+failures|do\s+not\s+run\s+tests|never\s+run\s+tests)\b", re.IGNORECASE),
        "Testing guidance conflicts with shortcuts that tell agents to ignore verification.",
        "Keep test expectations strict and move prototype exceptions into a narrow section.",
    ),
]


def iter_repo_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(dirname for dirname in dirs if dirname.lower() not in SKIP_DIRS)
        for filename in sorted(files):
            yield Path(current) / filename


def relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def is_instruction_file(path: Path) -> bool:
    if path.name in INSTRUCTION_NAMES:
        return True
    if path.name == "copilot-instructions.md" and ".github" in path.parts:
        return True
    parts = path.parts
    return ".cursor" in parts and "rules" in parts and path.suffix.lower() in {".md", ".mdc"}


def is_mcp_config(path: Path) -> bool:
    if path.name in MCP_NAMES:
        return True
    return path.name == "mcp.json" and any(part in {".cursor", ".vscode"} for part in path.parts)


def classify_context(path: Path, root: Path) -> tuple[str, int] | None:
    if is_instruction_file(path):
        return ("agent-instructions", 100)
    if is_mcp_config(path):
        return ("mcp-config", 95)
    lower = path.name.lower()
    if lower == "readme.md":
        return ("readme", 75)
    try:
        rel_parts = tuple(part.lower() for part in path.relative_to(root).parts)
    except ValueError:
        rel_parts = tuple(part.lower() for part in path.parts)
    if rel_parts and rel_parts[0] == "docs" and path.suffix.lower() in {".md", ".txt"}:
        return ("docs", 50)
    if lower in {"package.json", "pyproject.toml", "go.mod", "cargo.toml"}:
        return ("project-metadata", 45)
    return None


def line_number(text: str, match: re.Match[str]) -> int:
    return text.count("\n", 0, match.start()) + 1


def find_stale_markers(path: Path, root: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for match in STALE_RE.finditer(text):
        findings.append(
            Finding(
                rule_id="ACL-STALE-CONTEXT",
                severity="medium",
                message=f"Potential stale context marker: {match.group(0)}.",
                file=relative(path, root),
                line=line_number(text, match),
                suggestion="Remove stale instructions or move them into an explicitly archived section.",
            )
        )
    return findings[:8]


def find_duplicate_lines(path: Path, root: Path, text: str) -> list[Finding]:
    counts: dict[str, tuple[int, int]] = {}
    for index, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip().lower()
        if len(line) < 12 or line.startswith("#"):
            continue
        count, first_line = counts.get(line, (0, index))
        counts[line] = (count + 1, first_line)
    findings = []
    for line, (count, first_line) in sorted(counts.items()):
        if count >= 3:
            findings.append(
                Finding(
                    rule_id="ACL-DUPLICATE-CONTEXT",
                    severity="low",
                    message=f"Instruction line is repeated {count} times: {line[:80]}.",
                    file=relative(path, root),
                    line=first_line,
                    suggestion="Deduplicate repeated guidance so the agent sees one source of truth.",
                )
            )
    return findings


def find_conflicts(texts: list[tuple[Path, str]], root: Path) -> list[Finding]:
    combined = "\n".join(text for _, text in texts)
    findings: list[Finding] = []
    for rule_id, left_re, right_re, message, suggestion in CONFLICT_RULES:
        if not left_re.search(combined) or not right_re.search(combined):
            continue
        for path, text in texts:
            left_match = left_re.search(text)
            right_match = right_re.search(text)
            match = left_match or right_match
            if match:
                findings.append(
                    Finding(
                        rule_id=rule_id,
                        severity="high",
                        message=message,
                        file=relative(path, root),
                        line=line_number(text, match),
                        suggestion=suggestion,
                    )
                )
                break
    return findings


def extract_mcp_servers(path: Path, root: Path, text: str | None = None) -> tuple[list[McpServer], list[Finding]]:
    rel = relative(path, root)
    try:
        payload = json.loads(read_text(path) if text is None else text)
    except json.JSONDecodeError as exc:
        return [], [
            Finding(
                rule_id="ACL-MCP-JSON",
                severity="high",
                message=f"MCP config is not valid JSON: {exc.msg}.",
                file=rel,
                line=exc.lineno,
                suggestion="Fix the JSON before letting agents load MCP tools from this repo.",
                is_scan_error=True,
            )
        ]

    raw_servers = payload.get("mcpServers", payload.get("servers", {}))
    if not isinstance(raw_servers, dict):
        return [], [
            Finding(
                rule_id="ACL-MCP-SHAPE",
                severity="medium",
                message="MCP config does not contain an object under mcpServers or servers.",
                file=rel,
                suggestion="Use the standard mcpServers object so tools are auditable.",
                is_scan_error=True,
            )
        ]

    servers: list[McpServer] = []
    findings: list[Finding] = []
    for name, config in sorted(raw_servers.items()):
        if not isinstance(config, dict):
            findings.append(
                Finding(
                    rule_id="ACL-MCP-SERVER-SHAPE",
                    severity="medium",
                    message=f"MCP server `{name}` must be an object, got {type(config).__name__}.",
                    file=rel,
                    suggestion="Define each MCP server as an object with command, args, and optional env fields.",
                    is_scan_error=True,
                )
            )
            continue
        command = str(config.get("command", "")).strip()
        args = " ".join(str(item) for item in config.get("args", []) if item is not None)
        env = config.get("env", {})
        reasons: list[str] = []
        command_line = " ".join(part for part in [command, args] if part).strip()

        if command in {"bash", "sh", "zsh", "powershell", "pwsh", "cmd"}:
            reasons.append("shell command")
        if NETWORK_RE.search(command_line):
            reasons.append("network fetch")
        if "| sh" in command_line or "| bash" in command_line:
            reasons.append("pipe to shell")
        if re.search(r"(^|\s)/(?:\s|$)|--root\s+/", command_line):
            reasons.append("root filesystem scope")
        if isinstance(env, dict) and any(SECRET_RE.search(str(key)) for key in env):
            reasons.append("secret-like environment variable")
        if command in {"npx", "uvx", "docker"}:
            reasons.append("dynamic tool execution")

        risk = "low"
        high_risk_reasons = {
            "shell command",
            "network fetch",
            "pipe to shell",
            "root filesystem scope",
            "secret-like environment variable",
        }
        if any(reason in reasons for reason in high_risk_reasons):
            risk = "high"
        elif reasons:
            risk = "medium"

        servers.append(
            McpServer(
                name=str(name),
                command=command_line or "(missing command)",
                risk=risk,
                reasons=tuple(reasons),
                file=rel,
            )
        )
        if risk != "low":
            findings.append(
                Finding(
                    rule_id="ACL-MCP-RISK",
                    severity="high" if risk == "high" else "medium",
                    message=f"MCP server `{name}` has {risk} risk: {', '.join(reasons)}.",
                    file=rel,
                    suggestion=(
                        "Pin the tool, narrow filesystem/network scope, and avoid secret-bearing env unless required."
                    ),
                )
            )
    return servers, findings


def score_findings(findings: list[Finding]) -> int:
    penalties = {"high": 18, "medium": 9, "low": 3}
    total = sum(penalties.get(finding.severity, 5) for finding in findings)
    return max(0, 100 - total)


def has_scan_error(findings: list[Finding]) -> bool:
    return any(finding.is_scan_error for finding in findings)


def scan_repository(root: Path, budget_chars: int = 24000) -> ScanReport:
    root = root.resolve()
    context_files: list[ContextFile] = []
    findings: list[Finding] = []
    instruction_texts: list[tuple[Path, str]] = []
    mcp_servers: list[McpServer] = []
    total_context_chars = 0

    if not root.exists():
        finding = Finding(
            rule_id="ACL-MISSING-PATH",
            severity="high",
            message="Scan target does not exist.",
            file=str(root),
            suggestion="Fix the path before using this result as a CI gate.",
            is_scan_error=True,
        )
        return ScanReport(
            root=root,
            score=0,
            scan_error=True,
            findings=[finding],
            stats={
                "budget_chars": budget_chars,
                "files_scanned": 0,
                "context_files": 0,
                "instruction_files": 0,
                "mcp_configs": 0,
                "mcp_servers": 0,
                "high_risk_mcp_servers": 0,
                "total_context_chars": 0,
                "findings": 1,
                "scan_error": True,
            },
        )

    try:
        files = list(iter_repo_files(root))
    except OSError as exc:
        finding = Finding(
            rule_id="ACL-SCAN-ERROR",
            severity="high",
            message=f"Could not enumerate scan target: {exc}.",
            file=str(root),
            suggestion="Fix filesystem permissions or narrow the scan target.",
            is_scan_error=True,
        )
        return ScanReport(
            root=root,
            score=0,
            scan_error=True,
            findings=[finding],
            stats={
                "budget_chars": budget_chars,
                "files_scanned": 0,
                "context_files": 0,
                "instruction_files": 0,
                "mcp_configs": 0,
                "mcp_servers": 0,
                "high_risk_mcp_servers": 0,
                "total_context_chars": 0,
                "findings": 1,
                "scan_error": True,
            },
        )

    for path in files:
        classification = classify_context(path, root)
        if not classification:
            continue
        try:
            text = read_text(path)
        except OSError as exc:
            findings.append(
                Finding(
                    rule_id="ACL-READ-ERROR",
                    severity="medium",
                    message=f"Could not read context file: {exc}.",
                    file=relative(path, root),
                    suggestion="Fix permissions or remove the unreadable file from the default agent context path.",
                    is_scan_error=True,
                )
            )
            continue
        kind, priority = classification
        chars = len(text)
        total_context_chars += chars
        context_files.append(ContextFile(path=relative(path, root), kind=kind, chars=chars, priority=priority))
        if is_instruction_file(path):
            instruction_texts.append((path, text))
            findings.extend(find_stale_markers(path, root, text))
            findings.extend(find_duplicate_lines(path, root, text))
        if is_mcp_config(path):
            servers, mcp_findings = extract_mcp_servers(path, root, text)
            mcp_servers.extend(servers)
            findings.extend(mcp_findings)

    if not instruction_texts:
        findings.append(
            Finding(
                rule_id="ACL-MISSING-INSTRUCTIONS",
                severity="medium",
                message="No coding-agent instruction file was found.",
                file=".",
                suggestion=(
                    "Add AGENTS.md, CLAUDE.md, .github/copilot-instructions.md, "
                    "or a similar explicit agent entrypoint."
                ),
            )
        )

    findings.extend(find_conflicts(instruction_texts, root))

    if total_context_chars > budget_chars:
        findings.append(
            Finding(
                rule_id="ACL-CONTEXT-BUDGET",
                severity="medium",
                message=f"Agent context candidates use {total_context_chars} chars, above budget {budget_chars}.",
                file=".",
                suggestion="Move old notes out of the default context path or lower-priority docs.",
            )
        )

    context_files.sort(key=lambda item: (-item.priority, item.path))
    mcp_servers.sort(key=lambda item: (item.risk != "high", item.name))
    findings.sort(
        key=lambda item: (
            {"high": 0, "medium": 1, "low": 2}.get(item.severity, 3),
            item.file,
            item.line or 0,
            item.rule_id,
        )
    )

    scan_error = has_scan_error(findings)
    stats = {
        "budget_chars": budget_chars,
        "files_scanned": len(files),
        "context_files": len(context_files),
        "instruction_files": len(instruction_texts),
        "mcp_configs": sum(1 for item in context_files if item.kind == "mcp-config"),
        "mcp_servers": len(mcp_servers),
        "high_risk_mcp_servers": sum(1 for item in mcp_servers if item.risk == "high"),
        "total_context_chars": total_context_chars,
        "findings": len(findings),
        "scan_error": scan_error,
    }
    return ScanReport(
        root=root,
        score=score_findings(findings),
        scan_error=scan_error,
        findings=findings,
        context_files=context_files,
        mcp_servers=mcp_servers,
        stats=stats,
    )
