# Claude Code

Default profile: `interactive`.

Typical model: Claude Opus.

## MCP config

Copy `mcp-config.example.json` into Claude Code MCP settings (stdio). Set `TYPESAFE_API_KEY` in the environment.

For a shared Streamable HTTP daemon, start `jev-mcp --transport streamable-http` and copy `mcp-config.http.example.json`. Set `JEV_MCP_HTTP_TOKEN`.

Recommended first deployment:

```text
JEV_MCP_PROFILE=interactive
JEV_MCP_SHADOW_MODE=true
```

## Instructions

Copy `CLAUDE.example.md` into the target repository's `CLAUDE.md`, or merge the Jev section.

## Usage bias

Claude Code already has a human in the loop. Call Jev selectively when it avoids unnecessary Opus reasoning and helps the user decide the next attempt toward a predefined goal. Do not call Jev for trivial decisions that are obvious from deterministic evidence.
