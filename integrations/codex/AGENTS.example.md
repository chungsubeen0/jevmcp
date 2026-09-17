# Jev MCP

Jev is available as a low-cost probabilistic judgment service.

Use Jev for routine classification and evidence evaluation.
Do not use Jev to generate code or replace complex reasoning.

## Failure triage

For a non-trivial failing test, build, lint, or typecheck result,
prefer `jev_triage_failure` before performing broad investigation.

Use the result as evidence, not as proof.

## Repeated attempts

After two materially unsuccessful attempts against the same problem,
use `jev_compare_attempts`.

If the result indicates likely repetition without meaningful progress,
reconsider the root-cause hypothesis before making another similar edit.

## Completion

For large tasks with multiple explicit requirements,
use `jev_check_completion` before final completion review.

Investigate requirements flagged as uncertain or potentially incomplete.

## Context

When repository discovery produces many plausible candidates,
`jev_rank_context` may be used to prioritize inspection.

Do not permanently exclude lower-ranked context if higher-ranked
evidence proves insufficient.

## Boundaries

Never delegate architecture, code generation, novel debugging,
security conclusions, or ambiguous product decisions to Jev.
