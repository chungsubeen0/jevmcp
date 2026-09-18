# Codex Desktop

Default profile: `autonomous`.

Typical models: Astra, Sol, other high-capability Codex models.

## MCP config

Copy `mcp-config.example.json` into your Codex MCP settings (stdio). Set `TYPESAFE_API_KEY` in the environment, not in a committed file.

For a shared Streamable HTTP daemon, start `jev-mcp --transport streamable-http` and copy `mcp-config.http.example.json`. Set `JEV_MCP_HTTP_TOKEN`.

Recommended first deployment:

```text
JEV_MCP_PROFILE=autonomous
JEV_MCP_SHADOW_MODE=true
```

Shadow mode records Jev judgments without describing them as mandatory control actions.

## Instructions

Copy `AGENTS.example.md` into the target repository's `AGENTS.md`, or merge the Jev section.

## Usage bias

Codex large-task runs should call Jev aggressively for:

- failure triage
- repeated-attempt detection
- multi-requirement completion checks

Call with the user's predefined goal. Read `user_decision`. Jev helps
choose the next attempt. It does not write code, run tests, or certify merges.
