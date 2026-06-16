# Changelog

## v0.1.1 - 2026-06-16

- Fixes skipped directory traversal so ignored trees are pruned before scanning.
- Adds explicit `scan_error` reporting across the model, Markdown, full JSON, and command-specific JSON outputs.
- Marks scan-fatal findings with explicit `is_scan_error` metadata instead of deriving the contract from rule IDs.
- Makes deterministic read/config failures return CLI exit code `1` before any `--fail-under` threshold decision.
- Tightens `brief --max-chars` so tiny budgets never exceed the requested limit.
- Documents CI exit codes and adds regression coverage for scan errors, MCP shape errors, docs discovery, skipped-directory pruning, and JSON schemas.

## v0.1.0 - 2026-06-16

- Initial local-first release plan for `agent-context-lab`.
- Adds CLI scaffolding for context scanning, scoring, MCP risk review, context maps, and agent-ready briefs.
- Includes example repositories that cover clean, conflicting, risky-MCP, and bloated-context cases.
