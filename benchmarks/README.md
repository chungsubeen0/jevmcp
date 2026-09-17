# Benchmark corpus

Local fixtures for directional evaluation of Jev MCP tools.

Each dataset file contains cases with:

- `id`
- `tool`
- `input`
- `mock_answers` for offline runs
- `expected.signals` with `direction` and optional `min`/`max`
- `expected.uncertain_expected`
- `expected.notes`

Not every case has binary ground truth. Ambiguous engineering judgments are labeled as uncertain.

```bash
python scripts/benchmark.py --provider mock
python scripts/benchmark.py --provider typesafe
```

Live runs require `TYPESAFE_API_KEY`. Do not present Level B/C savings as exact frontier token reductions.
