# Agent Context Lab

Show what your coding agent will read, trust, repeat, or misuse before it edits your repo.

`agent-context-lab` is a local-first CLI for teams using Codex, Claude Code, Cursor, Copilot, or other coding agents. It scans agent instruction files, MCP config, and high-priority repo context, then returns a CI-friendly readiness score with exact fixes.

```bash
PYTHONPATH=src python3 -m agent_context_lab scan examples/conflicting-agent-repo --format markdown
```

```text
Score: 55/100
ACL-CONFLICT-ASK  AGENTS.md:3  Conflicting edit-permission guidance
ACL-CONFLICT-DEPS AGENTS.md:4  Dependency policy conflicts
ACL-STALE-CONTEXT AGENTS.md:6  Potential stale context marker: legacy
```

Use it before handing a repository to an agent, before merging instruction changes, or as a lightweight CI gate:

```bash
PYTHONPATH=src python3 -m agent_context_lab scan . --fail-under 85
```

## Why

Coding agents silently inherit stale instructions, conflicting rules, oversized context, and risky MCP tools before anyone notices.

This tool focuses on the layer that large eval, tracing, and repo-packing tools often skip: the repo-local instructions and tool config that shape the agent before the first model call.

It is intentionally small:

- No external AI API calls.
- No telemetry.
- Python standard library only.
- Markdown and JSON output for human review or CI.
- Deterministic exit codes for CI: `0` pass, `1` scan/read/config error, `2` score below `--fail-under`.

## Install

From a clone:

```bash
git clone https://github.com/alexzhu0/agent-context-lab.git
cd agent-context-lab
python3 -m pip install .
agent-context-lab scan examples/conflicting-agent-repo --format markdown
```

For development without installing:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m agent_context_lab scan examples/conflicting-agent-repo --format markdown
```

## Quickstart

Scan a repo and print a full readiness report:

```bash
PYTHONPATH=src python3 -m agent_context_lab scan examples/conflicting-agent-repo --format markdown
```

Gate a pull request:

```bash
PYTHONPATH=src python3 -m agent_context_lab scan . --format markdown --fail-under 85
```

Export JSON for another tool:

```bash
PYTHONPATH=src python3 -m agent_context_lab scan . --format json > agent-context-report.json
```

## Examples

Inspect context priority:

```bash
PYTHONPATH=src python3 -m agent_context_lab map examples/bloated-context-repo
```

Review MCP tool risk:

```bash
PYTHONPATH=src python3 -m agent_context_lab mcp examples/mcp-risk-repo
```

Output excerpt:

```text
MCP servers: 2
High-risk servers: 2
local-files  high  root filesystem scope
shell-runner high  shell command, network fetch, pipe to shell, secret-like environment variable
```

Generate a compact handoff brief for an agent run:

```bash
PYTHONPATH=src python3 -m agent_context_lab brief examples/bloated-context-repo --max-chars 1200
```

## API

The public surface is CLI-first in the `v0.1` series.

| Command | Purpose |
| --- | --- |
| `scan <path>` | Full readiness report with findings, context map, MCP risk, score, and optional `--fail-under` gate. |
| `score <path>` | Compact score and counts for scripts. |
| `map <path>` | Priority-ordered map of agent instructions, MCP config, README, docs, and project metadata. |
| `mcp <path>` | MCP server risk table with command, risk level, reasons, and source file. |
| `brief <path>` | Short AI-friendly handoff brief with top context and first fixes. |

Supported formats:

```bash
--format markdown
--format json
```

Current rule families:

- Missing agent instruction entrypoint.
- Conflicting permission, dependency, and test guidance.
- Stale markers such as `deprecated`, `legacy`, `outdated`, `todo`, and `fixme`.
- Repeated instruction lines.
- Context budget overflow.
- Invalid or risky MCP configs, including shell execution, network fetches, root filesystem scope, and secret-like environment variables.

## CI

GitHub Actions example:

```yaml
- name: Agent context gate
  run: PYTHONPATH=src python3 -m agent_context_lab scan . --format markdown --fail-under 85
```

`--fail-under` gates the computed readiness score after the scan succeeds.
Use the `scan` command for CI because it includes the full findings table and returns a hard failure when a target path, context file, or MCP config cannot be read deterministically.

Exit codes:

| Code | Meaning |
| ---: | --- |
| `0` | Scan completed and score is at or above `--fail-under`, or no threshold was set. |
| `1` | Scan did not complete cleanly because the path, a context file, or MCP config was unreadable or malformed. |
| `2` | Scan completed, but the score is below `--fail-under`. |

Use a lower threshold while introducing the gate to an existing repo, then raise it after cleaning stale instruction files.

## Differentiation

`agent-context-lab` is not a replacement for Langfuse, Opik, promptfoo, or Repomix.

- Tracing tools show what happened after an agent or LLM ran.
- Eval tools test model or prompt behavior.
- Repo packers prepare source context for a model.
- `agent-context-lab` checks whether the repo-local instructions and MCP tools are safe and coherent before the agent starts.

That makes it a companion to prompt regression, tracing, and repo-to-LLM context workflows, not a competing platform.

## FAQ

**Does this call external AI APIs?**

No. It reads local files and applies deterministic rules.

**Will it modify my repository?**

No. It is read-only.

**Can I use it in CI?**

Yes. Use `--fail-under <score>`. The command returns exit code `1` for deterministic scan failures and `2` when a clean scan scores below the threshold.

**Why does the example repo score poorly?**

The examples are fixtures. `conflicting-agent-repo`, `mcp-risk-repo`, and `bloated-context-repo` intentionally include problems so the report is easy to inspect.

## Contributing

Issues and pull requests are welcome when they include a concrete repository shape, command, expected output, and actual output.

Useful contributions:

- New deterministic rules for coding-agent instruction files.
- MCP config examples from real-world setups.
- Output format integrations such as SARIF or JUnit.
- Better examples for Codex, Claude Code, Cursor, Copilot, or other agent workflows.

## License

MIT
