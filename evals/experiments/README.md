# Frontier × Jev experiment

Run 30–50 substantial coding tasks in four configurations:

| Config | Setup |
| --- | --- |
| A | Frontier only |
| B | Frontier + `jev_triage_failure` |
| C | B + `jev_compare_attempts` |
| D | All Jev tools |

Primary cost:

```text
total inference cost
────────────────────────
successful completed task
```

Never present Level B/C proxies as exact token savings.

Each task repo should expose visible tests plus hidden acceptance tests the agent cannot see.
See `HIDDEN.md`.

Agent instruction quality (will Codex/Claude actually call Jev?) is scored from `integrations/*/AGENTS.example.md` and `CLAUDE.example.md`, not from Jev probabilities.
