# Jev MCP repository

Contributor notes for Claude Code working on this codebase.

## What this is

A local MCP server. Frontier agents call it for cheap probabilistic judgment. This repo's job is to keep that interface honest, fast, and secret-safe.

## Do not

- Add code-generation or file-mutation tools
- Treat `p > 0.5` as truth
- Hard-code TypeSafe prices into business logic
- Contact the TypeSafe API during server startup
- Put secrets in YAML examples or telemetry

## Preferred workflow

1. Read the relevant tool module and `engine.py` before changing judgment flow.
2. Keep questions as single evidence-grounded propositions.
3. Cover policy changes in `tests/unit/test_thresholds.py` and `test_profiles.py`.
4. Use `MockProvider` in unit tests. Live TypeSafe calls belong in optional integration tests.

Consumer-facing Claude Code instructions live in `integrations/claude-code/CLAUDE.example.md`.
