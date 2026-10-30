# Progress

Scope changed on 2026-10-30 to a one-week merged plan: see `docs/PLAN.md` and `docs/decisions/scope-change.md`.

## Done

- [x] Phase 0: setup
- [x] Phase 1: foundations and ingestion (Java service, kept as the front door)
- [x] Phase 2A: labelling guide and IE/GB generator
- [x] Phase 2B: all 8 countries, dev, calibration and frozen test splits, sample messages
- [x] Phase 2 hard set: reviewed by delegation to the AI, tagged `phase-2`. N = 40 (5 per country), AI-drafted and AI-verified, **not manually reviewed by the owner**. `data/splits/hard.jsonl` is built. See `docs/decisions/hard-set.md` and `docs/hard-set-verification.md`.

## The seven days (2026-10-30 onward)

- [x] Day 1: finish and build the hard set (real N = 40)
- [x] Day 2: Python rules engine for all 8 countries, tuned on dev only (`agent/rules`, `docs/decisions/rules-engine.md`; thresholds are placeholders until Day 5)
- [x] Day 3: small eval harness and rules-only results table (`evals/`, `docs/eval-results.md`; plan said `agent/eval/`, the code is in `evals/`)
- [x] Day 4: agent loop, grounding check, retries, routing, property tests (`agent/repair`, `docs/decisions/agent.md`, `docs/threat-model.md`; built and tested offline, no real API call yet)
- [ ] Day 5: three-way comparison, threshold on calibration, one final run on test, injection cases
- [ ] Day 6: MCP server and approval gate
- [ ] Day 7: README, results, resume bullets

Cut order if time runs short: MCP first, then injection cases, then threshold polish. Never cut the verifier, the three-way table or the README.

## Deferred (not abandoned)

| Old phase | Item | Reason |
|---|---|---|
| 3 | Java rules engine | Replaced by one Python rules engine (no duplicate validator). Uncommitted Java work in `service/` is not extended. |
| 3B | Message rebuild and CBPR+ validation layers | Not needed for the repair agent; no time in a week |
| 4 | Swift model and libpostal baselines | Setup cost too high; the comparison is now rules-only, LLM-only, full agent |
| 5 | Java LLM stage | The LLM now lives in the Python agent |
| 6 | Review screen, API and UI | Review is a Postgres queue plus the MCP server |
| 7 | RAG and repair memory | Not needed for the core claim; time |
| 8 | Kafka pipeline | A Postgres table is enough for the queue |
| 9 | Grafana, demo page, publish | Replaced by Day 7 README and results |

## Phase 1 notes

Built: repository layout, Docker Compose (PostgreSQL 16 with pgvector, Redis), Spring Boot 3 service on Java 21 (Maven wrapper), Flyway migrations, JAXB classes generated from the two XSDs, safe StAX ingestion, message-type detection from config, XSD validation, address job extraction, SHA-256 deduplication, `POST /v1/messages` and `GET /v1/messages/{id}`.

Not built, by design: rules engine, LLM, Kafka, RAG, `rule_cards` table, the other endpoints.

Decision records: `docs/decisions/` (`xsd-versions`, `maven-build`, `safe-xml-parsing`, `ingest-persistence`, `address-job-extraction`).

Things to know:
- The supplied XSDs use `PostalAddress27`, not the `PostalAddress24` in the spec; several maximum lengths differ. `docs/spec.md` is unchanged; `xsd-versions.md` lists the differences and the XSD is the source of truth from now on.
- One table was added beyond the spec's data model (`message_ingest_reports`), see `ingest-persistence.md`.

## Phase 2A notes

Built: `data/labelling-guide.md` (decisions applied, awaiting approval) and the IE/GB reverse generator in `data/generator/` with tests (`python -m pytest`), the project seed in `data/generator/SEED`, and `docs/decisions/synthetic-generator.md`.

Not built: the other six countries, the four splits, the frozen test split, the hard-set tooling, the message builder and the stats script (all Phase 2B).

Things to know:
- Typos in gold stay as written, abbreviations are not expanded in gold, and the scorer folds the allowlisted expansions (guide sections 9 and 10).

## Phase 2B notes

Built: generators for FR, DE, NL, CA, US and IN (labelling guide sections 12-18); the dev (600), calibration (400) and test (1,000) splits in `data/splits/` with `splits.manifest.json`; the frozen test hash (`test.sha256`) and `scripts/verify_frozen.py`; `scripts/check_splits.py`; the hard-set scaffold (`data/hard_set/*.yaml`, validator, converter to `hard.jsonl`); the message builder and 300 sample messages in `data/messages/` with `manifest.json`; `scripts/split_stats.py`. 341 generator tests (`python -m pytest` in `data/generator`).

Not built, by design: the hard set (done in the Day 1 review, see the top of this file), rules, evaluation harness, scorer, baselines.

Things to know:
- `data/splits/hard.jsonl` now holds the 40-entry hard set. Each country file holds two entries marked EXAMPLE, which are left out unless `--include-examples`. `build_hard_set.py` takes `--min-entries` (default 40).
- The disjointness check does not open `test.jsonl`; it uses address-key hashes recorded when the splits were built (see `docs/decisions/splits-and-messages.md`). `--include-test-file` is there for the owner.
- 25 of the 300 messages are XSD-invalid on purpose (`too_many_lines` fault); `manifest.json` says which.
- Calibration and test tiers are balanced to within one record per country, not exactly equal (400 and 1,000 do not divide by 3).
- New pinned dependencies: `lxml`, `PyYAML`.

## Phase 2B follow-up: postcode-to-town ties (2026-10-29)

Checked every postcode-to-town table against the GeoNames files. Found wrong ties in US (13 of 41 pairings contradicted), DE and IN, and a locality-to-outward-code gap in GB. Fixed: US, DE and IN now write only postcodes GeoNames lists for the town (100% confirmed); IN sectors and localities and GB localities use their own codes where GeoNames gives them; NL Amsterdam stops at 1098. dev, calibration, test and the sample messages were regenerated and the test split was re-frozen once, with the owner's approval (new `test.sha256`, `test.jsonl` not opened).

Decision records: `postcode-ties.md` (lists every pairing GeoNames does not confirm), `geonames-circularity.md`, and the re-freeze entry in `splits-and-messages.md`. Labelling guide section 19 awaits approval.

Things to know:
- The generator and the Phase 3 rules engine will both use GeoNames, so town and postcode accuracy on synthetic data is optimistic; the AI-drafted, AI-verified hard set is the independent check (N = 40) and must be reported beside it.
- The test split must not be regenerated again without the owner's explicit approval.


## Day 2 notes (2026-10-30)

Built: `agent/rules/` (ParseState with token spans, evidence and confidence; 15 small rules run in a configurable order; 8 country profiles as YAML; GeoNames gazetteer; XSD-driven lengths; hybrid fallback; routing ACCEPT / NEEDS_LLM / REVIEW; `allowlist.py` shared with the Day 4 grounding check; `scoring.py` for labelling guide section 10; CLI that refuses everything but dev and calibration), tests in `agent/tests/` including Hypothesis property tests, `agent/requirements.txt` (PyYAML, pytest, hypothesis).

Not built, by design: LLM, agent, MCP, threshold calibration, any run on test or on the hard set.

Things to know:
- Tuned on dev only. Dev was never held out, and it is generator-shaped and shares GeoNames with the engine, so dev accuracy is optimistic (`docs/decisions/rules-engine.md`). No accuracy number is in the docs until the Day 3 harness writes `eval_runs` records.
- Confidence thresholds and `max_adr_lines` are placeholders; the real CBPR+ hybrid limit must be confirmed (`docs/decisions/hybrid-address.md`).
- The gazetteer file is gitignored; tests use a small in-test gazetteer, and one test skips if `cities500.txt` is absent.

## Day 3 notes (2026-10-30)

Built: `evals/` (common system interface with `rules_only` and stubs for `llm_only` and `agent`; metrics with Wilson intervals, false-repair k/n and a hallucinated-value check for every system; guards; run records in `evals/results/`; `evals/report.py` generating `docs/eval-results.md`; `evals/smoke.py` and `.github/workflows/ci.yml`), `docs/decisions/eval-records.md`, `docs/results-changelog.md` (empty), `docs/decisions/hard-set-results.md` (generated). CLAUDE.md now says numbers come only from run records in `evals/results/`.

Not built, by design: LLM-only, the agent, MCP. The test split is refused by the harness, with or without `--final`, until it is enabled on Day 5.

Things to know:
- Rules-only was run on dev, calibration and the hard set; the numbers are in `docs/eval-results.md` and nowhere else.
- No engine change was made after seeing hard-set results (the changelog is empty).
- The CI smoke run uses no GeoNames file (it is not committed), so its baseline is lower than the local dev result and it only catches regressions in the non-gazetteer parts. The workflow has not run on GitHub yet.
- Calibration has been seen twice for reporting (Day 2 audit, Day 3 baseline); Day 5 threshold setting on it is slightly optimistic.

## Day 4 notes (2026-10-30)

Built: `agent/repair/` (validator with reason codes, grounding, support standard, four tools with strict schemas and a citation guard, a hand-written tool-use loop with limits in code, propose-then-verify pipeline, confidence from signals, idempotent worker), `agent/db/schema.sql` (agent_repairs, agent_steps, agent_queue), `agent/config/routing.yml` and `prices.yml`, the `agent` system in `evals/` (same interface and run records), `docs/decisions/agent.md`, `docs/threat-model.md`.

Not built, by design: MCP, RAG, Kafka, UI. The agent has not been run against the real API: no `ANTHROPIC_API_KEY` was available, so the dev smoke run (`--limit 30`) is still to do, and there is no spend. Tests use a scripted fake model and the real SDK objects over a mock transport.

Things to know:
- Model `claude-haiku-5-5` (checked 2026-10-30). The brief asked for temperature 0; this model rejects non-default sampling parameters and the SDK no longer takes `temperature`, so none is sent (`docs/decisions/agent.md`).
- The routing threshold (0.85) and the confidence weights are placeholders for Day 5, to be set on calibration. The AdrLine maximum is still the placeholder from the rules config; the CBPR+ limit must be confirmed.
- A field with no pattern, word-list or gazetteer support caps confidence below the threshold, so such a field is never auto-accepted, by the rules or by the model.
- The agent runs on dev only until Day 5; real runs need `--limit`, a run budget, an estimate, `--yes` above 50 and the owner's approval above 30 records.
