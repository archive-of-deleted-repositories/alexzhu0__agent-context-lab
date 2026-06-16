"""Command-line entrypoint for agent-context-lab."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .reporting import (
    render_brief,
    render_brief_json,
    render_context_map,
    render_context_map_json,
    render_json,
    render_markdown,
    render_mcp,
    render_mcp_json,
    render_score,
    render_score_json,
)
from .scanner import scan_repository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan coding-agent instructions, MCP config, and repo context into a CI-friendly readiness report."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("scan", "score", "map", "mcp", "brief"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("path", help="Repository or directory to inspect")
        subparser.add_argument("--format", choices=("markdown", "json"), default="markdown")
        subparser.add_argument("--budget-chars", type=int, default=24000)
        subparser.add_argument("--fail-under", type=int, default=None)
        if command == "brief":
            subparser.add_argument("--max-chars", type=int, default=4000)
    return parser


def render_report(command: str, path: str, output_format: str, budget_chars: int, max_chars: int = 4000) -> tuple[int, str, bool]:
    report = scan_repository(Path(path), budget_chars=budget_chars)
    if command == "scan" and output_format == "json":
        output = render_json(report)
    elif command == "score" and output_format == "json":
        output = render_score_json(report)
    elif command == "map" and output_format == "json":
        output = render_context_map_json(report)
    elif command == "mcp" and output_format == "json":
        output = render_mcp_json(report)
    elif command == "brief" and output_format == "json":
        output = render_brief_json(report, max_chars=max_chars)
    elif command == "score":
        output = render_score(report)
    elif command == "map":
        output = render_context_map(report)
    elif command == "mcp":
        output = render_mcp(report)
    elif command == "brief":
        output = render_brief(report, max_chars=max_chars)
    else:
        output = render_markdown(report)
    return report.score, output, bool(report.stats.get("scan_error"))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    score, output, scan_error = render_report(
        args.command,
        args.path,
        args.format,
        args.budget_chars,
        max_chars=getattr(args, "max_chars", 4000),
    )
    print(output)
    if scan_error:
        print(f"agent-context-lab: scan target failed: {args.path}", file=sys.stderr)
        return 1
    if args.fail_under is not None and score < args.fail_under:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
