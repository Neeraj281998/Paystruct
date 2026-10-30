# PayStruct + PayMend: one-week plan

Written 2026-10-30. This supersedes the 5-week plan in `docs/spec.md` (see `docs/decisions/scope-change.md`).

## Why a week

The owner has 14 months of visa left and needs a sponsored job. The project is time-boxed to one week, about 26 hours. The goal is a finished, measured, honestly described project, not a complete system.

## The design

Principle: **the AI proposes, plain code decides.**

- `service/` (Java 21, Spring Boot 3) stays as the ingestion front door: XML parsing, XSD validation, address jobs. It is **not extended**.
- `agent/` (Python 3.12) holds everything new. One language for rules and validation, so there is no duplicate Java validator.
  - **Rules engine** (Python, one YAML-driven profile per country, 8 countries). It is the agent's `parse_address` tool and the rules-only baseline.
  - **Agent**: a hand-written tool-use loop on the Claude API, no framework.
    - Tools: `parse_address` (our rules), `country_lookup`, `validate_candidate`, `submit_repair` (must cite which rules it used).
    - Limits enforced in code: max 8 tool calls per attempt, max 3 attempts per payment, a per-payment cost budget, timeouts.
    - Address text is untrusted data, never instructions. The model has no tool that approves or publishes.
  - **Verifier** (propose, then verify): a fix is accepted only if the deterministic validator passes **and** the grounding check passes. Grounding: every component appears in the original text; only the country code and an allowlisted set of abbreviation expansions may be added. Failures go back to the agent with reasons, up to 3 attempts.
  - **Routing**: valid, grounded and confident goes to `repaired`. Everything else goes to `human_review`. If no town is written, never derive one: leave `TwnNm` unset and send to review (labelling guide section 20).
  - **Queue**: a Postgres table, not Kafka.
  - **MCP server** (Python, FastMCP): `queue_stats`, `explain_rejection`, `propose_repair` (dry run), `approve_and_replay`. The last needs an approval token that only a separate human-run CLI can create. The server re-validates before publishing.
- **Evaluation**: rules-only vs LLM-only (no verification) vs the full agent, on the frozen test split, reported separately on the AI-drafted, AI-verified hard set. Plus about 15 prompt-injection cases and an "ambiguous, should go to human" slice.
  - Metrics: exact repair rate, field accuracy, **false-repair rate (the most important)**, human-review rate, injection resistance, cost per payment, p50 and p95 latency.

## Day plan

About 3.5 to 4 hours a day. Each day ends committed.

### Day 1: finish and build the hard set

- The review was delegated to the AI (2026-10-30): VERIFY items checked against public sources (`docs/hard-set-verification.md`), GUIDE? items decided by written principles (`docs/decisions/hard-set.md`). Files carry the header "AI-drafted and AI-reviewed against public sources; not manually reviewed by the project owner."
- Shrink the hard set to about 40 entries (about 5 per country), keeping the hard tags (`no_town`, `no_country`, reordered, typos, abbreviations) and at least 4 `no_town` entries. `build_hard_set.py` takes a configurable minimum (default 40).
- Report the real N in `data/splits/hard.jsonl`'s manifest line and in `docs/PROGRESS.md`. Do not round it up.
- **Done when:** `data/splits/hard.jsonl` exists, every file carries the AI-provenance header, the validator passes, and the real N is written down.

### Day 2: Python rules engine, all 8 countries

- `agent/rules/`: country profiles (IE, GB, FR, DE, NL, CA, US, IN), the rule chain, the output in `PstlAdr` shape, a unit test per rule.
- Tune on the **dev split only**. Do not read the hard set or `test.jsonl`.
- **Done when:** all 8 countries parse, every rule has a passing unit test, and a dev-split score is recorded.

### Day 3: small eval harness and rules-only table

- `evals/`: a scorer (exact repair, field accuracy, false repair, review rate; the allowlisted expansions fold per guide sections 9 and 10) and an run record in `evals/results/` for each run.
- Run rules-only on dev and calibration. No run on test.
- **Done when:** one command prints the rules-only results table from run record in `evals/results/`s.

### Day 4: agent loop, verifier, retries, routing

- Tool-use loop, the four tools, the limits, the grounding check, the retry-with-reasons loop, routing, the Postgres queue table.
- Property tests (jqwik-style, in Python with Hypothesis): grounding never accepts a component absent from the text; a `no_town` input never yields a town; limits are never exceeded.
- **Done when:** the agent repairs a handful of dev records end to end, limits and routing are covered by tests, and property tests pass.

### Day 5: three-way comparison, threshold, final run, injection

- Run rules-only, LLM-only (no verification) and the full agent on dev and calibration. Set the confidence threshold on **calibration only**.
- Write the ~15 injection cases and the ambiguous slice (neither is taken from test).
- One final run on the frozen test split, **once**, then the hard set (first time it is read for scoring, with your say-so). Record everything in run records in `evals/results/`.
- **Done when:** the three-way table exists with test and hard-set columns reported separately, with injection resistance and cost and latency, and every number traces to an run record in `evals/results/`.

### Day 6: MCP server and approval gate

- FastMCP server with the four tools. `approve_and_replay` requires a token created by a separate human-run CLI, and the server re-validates before publishing.
- Tests: no token, an expired token and a token for a different payment are all refused.
- **Done when:** a Claude client can call all four tools, and the refusal tests pass.

### Day 7: README, results, resume bullets

- README: results table (from run records in `evals/results/` only), architecture, how to run, what was cut and why, honest limits (synthetic data, GeoNames circularity).
- Resume bullets with measured numbers only.
- **Done when:** a stranger can clone, run the tests and reproduce the rules-only table from the README alone.

## Cut order if time runs short

1. MCP server (Day 6).
2. Injection cases.
3. Threshold polish.

**Never cut:** the verifier, the three-way table, the README.

## Deferred (not abandoned)

Kafka, RAG and repair memory, the review screen, the Phase 3B message rebuild and CBPR+ validation layers, the Swift model and libpostal baselines, the Java LLM stage, Grafana, the demo page. Reasons are in `docs/PROGRESS.md`.

## Rules that still hold

See `CLAUDE.md`. In particular: synthetic data only; the frozen test split is run once; the hard set is not read or tuned on until the owner says so; no number without an run record in `evals/results/`; no secrets in the repo; no CBPR+ certification claim.

## Swift timing

Swift has deferred Standards Release 2026 and expects to set new timing for structured addresses by December 2026. The date must be checked and dated against Swift's own announcement before anything is published.
