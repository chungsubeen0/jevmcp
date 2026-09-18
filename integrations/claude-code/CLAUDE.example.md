# Jev MCP

Jev provides inexpensive probabilistic judgments.

Use it selectively when doing so avoids unnecessary Opus reasoning.

Implementation work is a series of attempts toward a predefined goal
the user already set. Jev helps the user decide the next attempt.
Jev does not implement.

Prefer Jev for:

- triaging non-obvious failures (`jev_triage_failure`);
- comparing repeated unsuccessful attempts (`jev_compare_attempts`);
- checking multi-requirement completion (`jev_check_completion`);
- ranking what to inspect next (`jev_rank_context`);
- classifying a large set of findings.

Read `user_decision` on those tools. Present it to the user when
the next attempt is not already obvious.

Do not call Jev for trivial decisions that are immediately obvious
from deterministic evidence or when the user is actively directing
the next step.

Do not delegate implementation, architecture, complex debugging,
task planning, business planning, or product decisions to Jev.

Do not skip a failing test, drop a backlog item, or adopt a roadmap
because Jev looked confident. Treat probabilities as evidence, not a plan.
The user still decides whether the predefined goal is achieved.

Treat probabilities as evidence, not facts.
