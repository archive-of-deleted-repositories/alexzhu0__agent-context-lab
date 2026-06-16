"""Data shapes for agent-context-lab reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    message: str
    file: str
    line: int | None = None
    suggestion: str = ""
    is_scan_error: bool = False


@dataclass(frozen=True)
class ContextFile:
    path: str
    kind: str
    chars: int
    priority: int


@dataclass(frozen=True)
class McpServer:
    name: str
    command: str
    risk: str
    reasons: tuple[str, ...] = ()
    file: str = ""


@dataclass
class ScanReport:
    root: Path
    score: int
    scan_error: bool = False
    findings: list[Finding] = field(default_factory=list)
    context_files: list[ContextFile] = field(default_factory=list)
    mcp_servers: list[McpServer] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
