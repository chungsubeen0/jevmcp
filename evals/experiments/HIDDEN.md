# Hidden acceptance tests

Benchmark repositories MUST keep a hidden rubric:

```text
visible tests   → agent may run these
hidden tests    → scorer only
```

Otherwise `jev_check_completion` and the frontier model look better simply because they check the announced list.

Hidden tests measure actual implementation quality: missed requirements, regressions, and silent scope cuts.
