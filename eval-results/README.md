# Eval history

Every release writes:

```text
eval-results/
└── vX.Y.Z/
    ├── software.json
    ├── triage.json
    ├── stuck.json
    ├── completion.json
    ├── context.json
    ├── consistency.json
    ├── adversarial.json
    ├── codex.json
    ├── claude-code.json
    └── summary.md
```

Compare `jev-latest` drift against the last approved baseline. Code can stay identical while the hosted model changes.
