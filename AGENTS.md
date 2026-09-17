# Jev MCP repository

This repository implements a local MCP judgment server. It is not a coding agent.

## Product boundary

Jev MCP must not write production code, modify caller files, run shell commands, execute tests, create commits, approve merges, or certify correctness/security.

## Implementation rules

1. Use deterministic evidence first, then Jev, then frontier reasoning.
2. MCP tools depend on `JudgmentProvider`, never TypeSafe types directly.
3. Do not contact TypeSafe merely because the server starts.
4. Never return fabricated judgments if the provider fails. Return a structured error.
5. Never leak API keys, stack traces, or auth headers to MCP clients.
6. Do not return `APPROVED`, `CORRECT`, `SAFE_TO_MERGE`, or `SECURE`.
7. Context ranking must not delete candidates.
8. Thresholds and profiles are configurable. Profiles must not change tool schemas.
9. Cache keys exclude timestamp, session id, and client name unless they change the judgment.
10. Telemetry is local-only by default and stores hashes, not source, unless explicitly enabled.
11. Secrets and TypeSafe base_url come from the environment only. Project YAML cannot enable store_content.
12. Client metadata must not change profile or policy. Shadow mode defaults to on.

## Tests

Layers A–C and adversarial run on every PR. Live TypeSafe (Layer D) and hosted golden evals (Layer E) are nightly/release only.

Never assert exact Jev probabilities in unit tests. Unit tests ask: given these probabilities, does our software behave?

Schema snapshots in `tests/contract/snapshots/tools.json` are part of the agent-facing API.

For Codex Desktop consumer instructions, see `integrations/codex/AGENTS.example.md`.
