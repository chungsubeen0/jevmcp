# Jev MCP

Jev is a low-cost probabilistic judgment service.

Implementation work is a series of attempts toward a predefined goal
the user already set. Jev helps the user decide the next attempt.
Jev does not generate code or replace complex reasoning.

## Implementation loop

Keep the goal fixed. Do not ask Jev to invent or change it.

1. After a non-trivial failing test, build, lint, or typecheck,
   call `jev_triage_failure` before broad investigation.
   Read `user_decision`. The failing check stays in scope.

2. After two materially unsuccessful attempts against the same
   problem, call `jev_compare_attempts` with the same `task_goal`.
   Read `user_decision` and `control_signal`.
   The user (or frontier, acting for the user) picks the next attempt.

3. When discovery produces many plausible files or stories,
   call `jev_rank_context`. Inspect HIGH first. Do not drop the rest.

4. For a large task with explicit requirements, call
   `jev_check_completion` before an expensive full-task review.
   `INCOMPLETE` means keep implementing listed requirements.
   `APPEARS_COMPLETE` is not a ship decision.

5. When a change looks sensitive, call `jev_assess_risk`.
   The user decides whether to buy a real review.

6. A large finding pile: `jev_classify_findings`.
   Likelihoods only. User decides what to act on.

Use each result as evidence, not as proof.

## Boundaries

Never delegate architecture, code generation, novel debugging,
security conclusions, task planning, business planning, or
ambiguous product decisions to Jev.

Do not skip a failing test, drop a backlog item, or ship a plan
because Jev returned a HIGH or LOW probability. Jev ranks and
triages evidence. The frontier still writes the code and the plan.
The user still decides whether the predefined goal is achieved.
