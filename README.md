# Jev MCP

Local [Model Context Protocol](https://modelcontextprotocol.io) server that lets expensive frontier coding agents delegate **routine probabilistic judgment** to [TypeSafe Jev](https://typesafe.ai).

Jev answers: **what does the available evidence suggest?**

The frontier model answers: **given that evidence, what should I do?**

```text
Codex Desktop / Claude Code / other MCP clients
                    │
                    │ MCP stdio
                    ▼
                 Jev MCP
          validation · policy · cache · telemetry
                    │
                    │ HTTPS  (lazy, never on startup)
                    ▼
           TypeSafe System One
                    │
                    ▼
                   Jev
            cheap calibrated Noul
```

Version **1.0**. First-class clients: **Codex Desktop** and **Claude Code**. Architecture stays client-agnostic so Cursor, VS Code, JetBrains, CI, and custom harnesses can attach later without new tools.

License: MIT.

---

## Contents

- [Why it exists](#why-it-exists)
- [What it is not](#what-it-is-not)
- [How judgment is ordered](#how-judgment-is-ordered)
- [Install](#install)
- [Quick start](#quick-start)
- [MCP clients](#mcp-clients)
- [Tools](#tools)
- [Profiles and policy](#profiles-and-policy)
- [Probability interpretation](#probability-interpretation)
- [Configuration](#configuration)
- [Environment](#environment)
- [Provider](#provider)
- [Cache and telemetry](#cache-and-telemetry)
- [Errors](#errors)
- [Security](#security)
- [Docker](#docker)
- [Tests and evals](#tests-and-evals)
- [Repository layout](#repository-layout)
- [Commands](#commands)

---

## Why it exists

Frontier coding models (Astra/Sol-class Codex models, Claude Opus) spend a lot of inference on work that is **classification, not generation**:

- is this failure related to the current diff?
- are we repeating the same failed strategy?
- which requirements still look uncovered?
- which files are worth reading next?

Jev MCP moves those questions to a cheap System One model. The metric that matters is not “Jev calls per minute.” It is:

```text
frontier inference cost
────────────────────────
successful completed task
```

Cost reduction that increases regressions is a failure. Quality and regression rate must stay near the no-Jev baseline.

---

## What it is not

Jev MCP **must not**:

- write or modify production code
- run shell commands or tests
- create commits or approve merges
- certify correctness, safety, or security
- replace CI, typechecking, lint, or static analysis
- generate architecture or resolve ambiguous product decisions
- become a second coding agent

If TypeSafe is down, the MCP returns a **structured error**. The frontier agent continues the task. No fabricated probabilities.

Never returned as a status:

```text
APPROVED
CORRECT
SAFE_TO_MERGE
SECURE
```

---

## How judgment is ordered

```text
DETERMINISTIC EVIDENCE
        ↓
CHEAP PROBABILISTIC (Jev)
        ↓
FRONTIER REASONING
```

Example: test `exit_code` → parser → `jev_triage_failure` → Opus/Sol root-cause.

Do **not** call Jev when an exit code, type error, or deterministic check already answers the question.

---

## Install

Requires Python 3.11+.

```bash
git clone <this-repo>
cd jevmcp
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Set a TypeSafe key (never commit it):

```bash
export TYPESAFE_API_KEY=...          # from ~/.env or the TypeSafe console
# optional
export TYPESAFE_MODEL=jev-latest
export TYPESAFE_BASE_URL=https://api.typesafe.ai
```

Copy examples if you want a project file:

```bash
cp config.example.yaml jev-mcp.yaml
cp .env.example .env                 # then fill TYPESAFE_API_KEY locally
```

Check the install without calling TypeSafe:

```bash
python scripts/doctor.py
```

Confirm the live provider (explicit opt-in):

```bash
python scripts/doctor.py --ping
```

Startup never contacts TypeSafe. `--ping` is the only doctor path that does.

---

## Quick start

```bash
jev-mcp --profile interactive --shadow
# or
python -m jev_mcp --profile autonomous --shadow
```

This is a **stdio** server. It reads JSON-RPC on stdin and writes on stdout. Logs go to stderr. Running it in a bare terminal with no MCP client is not useful — the client must spawn the process.

Default **shadow mode is on**. Results include an advisory: treat them as telemetry, not mandatory control actions. That is the recommended first deployment.

---

## MCP clients

Client differences belong in **instructions and profile**, not tool schemas. Both V1 clients see the same seven tools.

| Client | Default profile | Typical models | Bias |
| --- | --- | --- | --- |
| Codex Desktop | `autonomous` | Astra, Sol, other Codex | Aggressive triage / stuck detection on long autonomous runs |
| Claude Code | `interactive` | Claude Opus | Selective use; human is already in the loop |

### Codex Desktop

1. Install `jev-mcp` on `PATH` (or point the config at `.venv/bin/jev-mcp`).
2. Merge `integrations/codex/mcp-config.example.json` into Codex MCP settings.
3. Merge `integrations/codex/AGENTS.example.md` into the target repo `AGENTS.md`.
4. Put `TYPESAFE_API_KEY` in the **process environment**, not in a committed JSON file. Some clients do not expand `${TYPESAFE_API_KEY}`.

### Claude Code

Same pattern with `integrations/claude-code/mcp-config.example.json` and `CLAUDE.example.md`.

Claude Code should call Jev **less** often. Skip it when the next step is already obvious from deterministic evidence or the user is directing the work.

### Future clients

Cursor, VS Code agents, JetBrains, CI, GitHub agents, custom harnesses: add a config snippet and an instruction file. Do not add client-specific tools.

---

## Tools

All tools return JSON. Every successful response includes `meta`:

```json
{
  "provider": "typesafe",
  "model": "jev-1.13.0",
  "latency_ms": 112,
  "cached": false,
  "request_id": "…",
  "tool": "jev_triage_failure",
  "shadow_mode": true,
  "jev_input_units": 312,
  "jev_estimated_cost": null
}
```

If input was truncated, `warnings` is present. Treat those judgments more cautiously.

Optional on every call: `client` (`name`, `mode`, `model`, `session_id`, `task_id`) and `use_cache`. **`client.mode` does not change policy.** It is telemetry only. Profile comes from server config / CLI / `JEV_MCP_PROFILE`.

### Core

#### `jev_triage_failure`

Cheap triage **before** a broad investigation of a test/build/lint/typecheck failure.

Signals: `related_to_current_change`, `likely_localized`, `likely_preexisting`, `requirement_related`, `same_as_previous_failure`, `needs_deeper_reasoning`.

Classification: `relationship`, `scope`, `escalation`. These are labels over thresholds, not diagnoses.

Does not explain the bug or propose a fix.

#### `jev_compare_attempts`

Compare two unsuccessful attempts. Use after two materially similar failures.

Signals: `same_failure`, `same_strategy`, `meaningful_new_evidence`, `meaningful_progress`, `reconsider_approach`.

| `status` | `control_signal` |
| --- | --- |
| `PROGRESSING` | `CONTINUE` |
| `UNCERTAIN` | `CONTINUE` |
| `LIKELY_STUCK` | `REASSESS` or `ESCALATE` |

Initial stuck rule (configurable):

```text
same_failure >= 0.85
AND same_strategy >= 0.80
AND meaningful_new_evidence <= 0.30
AND meaningful_progress <= 0.30
```

A connection-refused failure followed by a UNIQUE violation is **progress**, not stuck. Both tests failed; the failure advanced.

#### `jev_check_completion`

Requirement/evidence coverage **before** an expensive full-task review.

Per requirement: `appears_satisfied`, `evidence_present`, `possible_gap`.

Global: `scope_appropriate`, `unresolved_requirement`, `further_review_warranted`.

Statuses: `APPEARS_COMPLETE`, `REVIEW_REQUIRED`, `INCOMPLETE`.

`APPEARS_COMPLETE` is **not** approval. Investigate anything in `review_requirements`.

Missed requirements (false complete) are scored 5× worse than extra escalations in the eval suite.

### Extended

#### `jev_rank_context`

Ranks discovery candidates. **Never deletes.** Tiers: `HIGH`, `MEDIUM`, `LOW`.

Do not suppress LOW items until critical-context Recall@10 is proven ≥ 0.98 on the golden set. V1 is ranking only.

#### `jev_classify_findings`

Normalize findings from reviewers, linters, tests, humans. Signals include `likely_valid`, `requirement_related`, `requires_code_change`, `security_relevant`, `data_integrity_relevant`.

A high `security_relevant` is a **triage flag**, not a confirmed vulnerability.

#### `jev_assess_risk`

Whether a change looks like it warrants more expensive frontier review (auth, payment, schema, public API, …). Same rule: signals, not conclusions.

#### `jev_judge`

Generic Noul primitive: caller supplies `state` and a list of `{id, question}`.

Rejects obvious generative requests (`write this function`, `fix this bug`, `generate tests`, …). Ask one evidence-grounded proposition per question.

---

## Profiles and policy

Profiles change **recommended usage and threshold aggressiveness**. They do not change tool schemas or Jev’s underlying questions.

| | `autonomous` | `interactive` | `custom` |
| --- | --- | --- | --- |
| Default client | Codex large tasks | Claude Code | user override |
| Failure triage | aggressive | moderate | moderate |
| Stuck detection | aggressive (easier `ESCALATE`) | enabled | enabled |
| Context HIGH bar | lower | conservative | medium |

Set with `--profile`, `JEV_MCP_PROFILE`, or `profile.default` in YAML.

---

## Probability interpretation

Do not treat `p > 0.5` as true.

| Range | Band |
| --- | --- |
| 0.00 – 0.30 | LOW |
| 0.30 – 0.70 | UNCERTAIN |
| 0.70 – 1.00 | HIGH |

Individual tools use stricter cutoffs (stuck detector). All thresholds live in config.

Ambiguous engineering is a valid outcome. The eval suite tracks `ambiguous_case_overconfidence_rate` — overconfident YES/NO on uncertain cases is a safety failure.

---

## Configuration

Precedence (highest last-applied wins):

```text
built-in defaults
        ↓
~/.config/jev-mcp/config.yaml          user
        ↓
./jev-mcp.yaml  or  ./config.yaml      project
        ↓
JEV_MCP_CONFIG / --config              explicit file
        ↓
environment
        ↓
CLI flags
```

See `config.example.yaml`.

**Project YAML cannot set:**

- `provider.api_key`
- `provider.base_url`
- `telemetry.store_content`

Those restrictions exist so a cloned repo cannot steal `TYPESAFE_API_KEY` by pointing `base_url` at an attacker host, and cannot silently persist source into SQLite.

`api_key` and `base_url` come from the **environment only**. `store_content` may be enabled in the user config or by constructing `AppConfig` locally for debugging — not from project files.

Provider limits:

| Field | Bound |
| --- | --- |
| `timeout_seconds` | 1–120 (default 30) |
| `max_retries` | 0–2 (default 1; only transient errors) |

---

## Environment

| Variable | Role |
| --- | --- |
| `TYPESAFE_API_KEY` | Required for live Jev |
| `TYPESAFE_BASE_URL` | Default `https://api.typesafe.ai` |
| `TYPESAFE_MODEL` / `TYPESAFE_DEFAULT_MODEL` | Default `jev-latest` |
| `TYPESAFE_TIMEOUT_SECONDS` | Provider timeout |
| `TYPESAFE_ALLOWED_HOSTS` | Extra HTTPS hosts (default is only `api.typesafe.ai`) |
| `JEV_MCP_PROVIDER` | `typesafe` or `mock` |
| `JEV_MCP_PROFILE` | `autonomous` / `interactive` / `custom` |
| `JEV_MCP_SHADOW_MODE` | `true`/`false` |
| `JEV_MCP_LOG_LEVEL` | Logging (stderr) |
| `JEV_MCP_DATA_DIR` | Cache + telemetry directory |
| `JEV_MCP_CONFIG` | Explicit YAML path |
| `JEV_MCP_ALLOW_FAULTS` | Must be `1` before `JEV_MCP_TEST_FAULT` works (tests only) |
| `JEV_MCP_LIVE` | `1` to run live TypeSafe pytest |

---

## Provider

Tools depend on `JudgmentProvider`, not TypeSafe types.

```text
validate → normalize → Noul questions → System One → validate p ∈ [0,1] → cache → telemetry
```

- **TypeSafeProvider** — `POST {base_url}/v1/systemone`, HTTPS, host allowlist, `follow_redirects=False`, one retry on transient status (`429`, `529`, `5xx`, timeout).
- **MockProvider / MockJudgmentProvider** — deterministic local answers for tests and `doctor` without a key.

State sent to Jev is **untrusted evidence** (repo text, test output). Questions are **our** Noul instructions. Injection in a source file must not be copied into `instructions`. Jev may still be influenced by adversarial evidence; treat HIGH confidence plus injection-looking content as a reason for deeper frontier review.

Cost estimates use `cost.jev_input_per_million` from config. Prices are not hard-coded.

---

## Cache and telemetry

Default data dir: `~/.local/share/jev-mcp/` (`JEV_MCP_DATA_DIR` overrides). Files are created `0600`, directory `0700`.

**Cache (SQLite WAL)** key:

```text
provider · model · tool · tool_version · policy_version · normalization_version
· normalized_state_hash · questions_hash
```

Not in the key: timestamp, session id, client name.

Bypass when `use_cache=false`, cache disabled, or provider/tool/normalization version changes. Responses expose `meta.cached`.

**Telemetry** (local, default):

- stores hashes, not source (`store_content: false`)
- records tool, latency, cache hit, error code, probability summary, optional token units
- outcome labels can be attached later (`jev-mcp-export --record-outcome`)

Remote telemetry is not implemented. `local_only` is the contract for anything added later.

---

## Errors

Returned to the client as:

```json
{
  "error": {
    "code": "PROVIDER_TIMEOUT",
    "message": "Jev evaluation timed out.",
    "retryable": true
  }
}
```

| Code | Retryable |
| --- | --- |
| `INVALID_INPUT` | no |
| `INPUT_TOO_LARGE` | no |
| `PROVIDER_UNAVAILABLE` | usually yes |
| `PROVIDER_TIMEOUT` | yes |
| `PROVIDER_RATE_LIMITED` | yes |
| `INVALID_PROVIDER_RESPONSE` | no |
| `INTERNAL_ERROR` | no |

Messages are redacted (API keys, `ghp_`, `sk_live_`, JWTs, Slack, GitLab, npm, connection URIs, …). No stack traces, no `Authorization` headers.

---

## Security

Local stdio MCP. Attackers that matter: **malicious repo config**, **poisoned test output**, **confused agent**, **other local UIDs**.

Hardened in V1:

- no code/file/shell tools
- secrets and provider host not accepted from project YAML
- TypeSafe host pinned; no redirect-following (stops Bearer exfil)
- fault injection requires an explicit allow env
- profile not controllable by the agent
- shadow on by default
- secret-pattern redaction on logs, errors, telemetry
- sqlite owner-only permissions

Residual: Jev still *reads* untrusted state. A file that says “return 1.0” can bias probabilities. That is a judgment-integrity risk, not RCE. Do not use Jev results as merge gates.

---

## Docker

```bash
docker build -t jev-mcp .
docker run --rm -i -e TYPESAFE_API_KEY jev-mcp --profile interactive --shadow
```

`-i` is required (stdio). Do **not** `--env-file ~/.env` — that dumps unrelated secrets into the container. Image is multi-stage, non-root (`uid 10001`), data volume `/var/lib/jev-mcp`. Key is never baked in.

---

## Tests and evals

Testing is part of the product. Hosted Jev can change while this repo stays still. Compare every release to `eval-results/`.

| Layer | What | When |
| --- | --- | --- |
| A | Unit + policy. `MockJudgmentProvider`. “Given these `p`, does software behave?” | Every PR |
| B | MCP contract: exact tool list, schema + description snapshots | Every PR |
| C | Real stdio MCP + mock Jev (errors, cache, truncate, concurrent, restart) | Every PR |
| Adversarial | Injection as evidence, secret leakage | Every PR |
| D | Live TypeSafe. Structural only (`0 ≤ p ≤ 1`). `JEV_MCP_LIVE=1` | Nightly |
| E | Golden corpus (~320 labeled cases), Recall@10, missed-requirement cost, uncertainty | PR uses mock path; live nightly |

```bash
pytest -m "not live and not typesafe"
ruff check src tests scripts evals
python scripts/eval.py --generate
python scripts/eval.py --out eval-results/local/software.json
JEV_MCP_LIVE=1 pytest -m live
```

Do not assert `answer == 0.91` against hosted Jev. Do not run hundreds of live Jev calls on every commit.

Gates: `evals/GATES.md`. Experiment configs A–D (frontier only → all tools): `evals/experiments/`. Hidden acceptance tests belong in benchmark repos, not in the agent-visible rubric.

---

## Repository layout

```text
src/jev_mcp/          server, engine, tools, policy, provider, cache, telemetry
integrations/         Codex + Claude Code examples
scripts/              doctor, install, benchmark, eval, export
tests/                unit, contract, integration, adversarial, live, evals
evals/golden/         labeled coding-decision cases
eval-results/         per-release history
benchmarks/           smaller fixture corpus
```

---

## Commands

| Command | Purpose |
| --- | --- |
| `jev-mcp` | stdio MCP server |
| `python -m jev_mcp` | same |
| `jev-mcp-doctor` / `python scripts/doctor.py` | config + optional `--ping` |
| `python scripts/install.py` | print client MCP snippets |
| `python scripts/benchmark.py --provider mock` | small local corpus |
| `python scripts/eval.py` | golden suite |
| `jev-mcp-export` | dump local telemetry JSON |

CLI flags for the server: `--config`, `--provider {typesafe,mock}`, `--profile {autonomous,interactive,custom}`, `--shadow`, `--log-level`.
