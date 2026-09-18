# Pilot Coding-Task Fixtures

This directory contains five compact, dependency-free Python coding tasks used
to exercise different agent work patterns.

## Fixture contract

Each fixture has this layout:

- `fixture.json`: scorer metadata, including whether visible tests initially pass.
- `public/TASK.md`: instructions shown to the coding agent.
- `public/<package>/`: the source package the agent may change.
- `public/tests/`: visible `unittest` coverage available to the agent.
- `hidden/`: deterministic scorer-only `unittest` coverage.

The harness **must copy only the contents of `public/` into the agent
workspace**. After the agent has completed the task, the harness injects the
fixture's `hidden/` tests and runs both suites. Hidden files must never be
present while the agent is working.

All fixtures use only the Python standard library. Run a fixture from its
directory with:

```sh
PYTHONPATH=public python3 -m unittest discover -s public/tests -v
PYTHONPATH=public python3 -m unittest discover -s hidden -v
```

Every initial fixture intentionally violates at least one visible or hidden
requirement. Intended repairs are local, and hidden tests avoid clocks,
networks, randomness, and third-party services.
