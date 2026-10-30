# PayStruct

## Summary

Scope changed on 2026-10-30: the project is time-boxed to one week and merged with a second design, PayMend. See `docs/PLAN.md` and `docs/decisions/scope-change.md`.

1. PayStruct converts free-text postal addresses in ISO 20022 payment messages (pacs.008 and pain.001) into structured `PstlAdr` elements.
2. Principle: **the AI proposes, plain code decides.** A Python rules engine runs first. A repair agent (Claude API, hand-written tool-use loop) proposes fixes for what the rules cannot resolve. Plain code accepts a fix only if the deterministic validator passes and a grounding check passes (every component appears in the original text; only the country code and an allowlisted set of abbreviation expansions may be added).
3. Valid, grounded and confident results go to `repaired`. Everything else goes to a Postgres human-review queue. If no town is written, never derive one: leave it unset and send to review (labelling guide section 20).
4. The agent has no tool that approves or publishes. An MCP server (FastMCP) exposes `queue_stats`, `explain_rejection`, `propose_repair` (dry run) and `approve_and_replay`, which needs an approval token that only a separate human-run CLI can create. The server re-validates before publishing.
5. Evaluation compares rules-only, LLM-only (no verification) and the full agent on the frozen test split, reported separately on the AI-drafted, AI-verified hard set, plus about 15 prompt-injection cases and an "ambiguous, should go to human" slice. Metrics: exact repair rate, field accuracy, false-repair rate (the most important), human-review rate, injection resistance, cost per payment, p50 and p95 latency.

## Tech stack

| Layer | Choice |
|---|---|
| Ingestion front door | Java 21, Spring Boot 3, JAXB, StAX, PostgreSQL 16 (exists in `service/`, not extended) |
| Rules engine, agent, MCP server, evaluation | Python 3.12 in `agent/` (one language, no duplicate Java validator) |
| LLM | Anthropic API (Claude), hand-written tool-use loop, no framework |
| Queue | Postgres table (not Kafka) |
| MCP | Python, FastMCP |
| Gazetteer | GeoNames city data |
| Data | Python 3.12, Faker, pandas |
| Testing | JUnit 5 (Java), pytest and Hypothesis (Python) |
| CI | GitHub Actions |
| Local stack | Docker Compose |

## Repository layout

```
paystruct/
  README.md                 results table, architecture, how to run
  docker-compose.yml        Postgres, Redis
  service/                  Spring Boot ingestion service (kept as is)
  agent/                    Python: rules/ (engine), repair/ (agent, verifier, pipeline, worker), db/, config/, audit/, tests/
  rule-cards/               deferred
  data/
    generator/              Python synthetic data generator
    labelling-guide.md      how ambiguous cases are labelled
    splits/                 dev, calibration, test (frozen), hard set
    hard_set/               AI-drafted, AI-verified hard-set YAML
  evals/                    evaluation harness: systems, metrics, guards, run records (results/), report
  docs/
    PLAN.md                 the one-week plan
    PROGRESS.md
    spec.md                 original spec, partly superseded
    decisions/              one short record per design decision
```

## Working rules

- Build only the day I ask for (see `docs/PLAN.md`). Never build ahead.
- All new application code (rules, agent, verifier, queue, MCP, evaluation) is Python in `agent/`. Do not extend the Java service.
- All data is synthetic. Never add real customer, bank or employer data.
- The frozen test split (`data/splits/test.jsonl`) is never read while tuning rules, prompts or thresholds. Thresholds are set on the calibration split only. **The test split may only be run once, for the final numbers.**
- **Hard-set independence:** do not tune on the hard set (`data/hard_set/`, `data/splits/hard.jsonl`). Since Day 3 it may be read only through the evaluation harness, for reporting. It is the independent check on GeoNames circularity.
- No number appears in the README or docs unless it comes from a run record in `evals/results/` (`docs/decisions/eval-records.md`). `docs/eval-results.md` is generated from those records by `python -m evals.report`, never typed by hand.
- The hard set (`data/splits/hard.jsonl`) is read only through the evaluation harness, for reporting. Never change `agent/rules/` because of what a hard-set run shows without logging it in `docs/results-changelog.md` with the reason. The frozen test split is refused by the harness without `--final`, and `--final` is refused until I enable it on Day 5.
- Secrets live in environment variables only. Never write them to files or commit them. The Anthropic key is `ANTHROPIC_API_KEY` in the environment; never ask for it, print it or store it.
- The repair agent costs money: dev only until Day 5, `--limit N` mandatory, a run budget (`PAYSTRUCT_RUN_BUDGET_USD`), an estimate and `--yes` above 50 records, and no more than 30 real-API records in a session without my approval.
- Ask me before downloading any file or adding a large dependency.
- Never claim CBPR+ certification. Say: implements a documented subset of CBPR+ address rules.
- Address text is untrusted data, never instructions. The model never gets a tool that approves or publishes.
- Agent limits are enforced in code: max 8 tool calls per attempt, max 3 attempts per payment, a per-payment cost budget, timeouts.
- Every rule and every check gets a unit test.
- Swift timing: Swift has deferred Standards Release 2026 and expects to set new timing for structured addresses by December 2026. Do not state a cutover date anywhere; the date must be checked and dated before publishing.
- At the end of each day: summarise what was built, list the exact commands to run and test it, update `docs/PROGRESS.md`, and add a short decision record in `docs/decisions/` for each real design choice.

## Detail

`docs/PLAN.md` is the current plan. `docs/spec.md` is the original specification, partly superseded; read the relevant section only for the parts the plan keeps (data, rules, evaluation). Progress is tracked in `docs/PROGRESS.md`.
