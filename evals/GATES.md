# Quality gates

Set exact Jev accuracy numbers after the first approved baseline. Do not invent percentages.

## Every PR

- unit (Layer A, including threshold boundaries)
- MCP contract / schema snapshots
- MCP protocol integration with mock provider
- adversarial + secret leakage
- typecheck/lint (`ruff`)
- golden software path (mock answers, not Jev intelligence)

## Nightly / manual

- live TypeSafe provider
- golden evals
- consistency suite
- calibration / uncertainty

## Release

- all deterministic tests
- provider smoke
- full golden eval
- Codex MCP smoke
- Claude Code MCP smoke
- performance regression vs last `eval-results/v*`

## Production-ready bar

- software tests: 100% pass
- MCP contract: 100% pass
- critical error paths covered
- no significant golden regression from approved baseline
- very low missed-requirement rate (false complete costs 5×)
- context ranking: critical Recall@10 >= 0.98 before any suppression
- stuck detection: low false-positive rate
- uncertain cases: overconfidence below agreed threshold
- secrets: zero leakage
- provider failure never blocks the frontier agent
