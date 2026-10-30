# Scope change: one-week merged plan

Date: 2026-10-30. Status: accepted.

## Why

- The owner has 14 months of visa left and needs a sponsored job. A five-week build no longer fits; the project is time-boxed to one week (about 26 hours).
- A finished, measured, honestly described project is worth more in a job search than a larger unfinished one.
- A second design, PayMend (an AI repair agent), fits the same problem. The two are merged under one principle: the AI proposes, plain code decides.

## Kept

- Synthetic data, the labelling guide, the generator, the dev, calibration and frozen test splits, the hand-written hard set (shrunk to about 40 entries; the real N is reported).
- The Java/Spring Boot ingestion service as the front door, unchanged and not extended.
- The working rules: synthetic data only, frozen test split, no number without an `eval_runs` record, no secrets in the repo, no CBPR+ certification claim.
- Deterministic rules first, then the LLM, then verification (grounding, validation), then human review.

## Changed

- One language for logic: the rules engine, agent, verifier, queue code, MCP server and evaluation are Python in `agent/`. No duplicate Java validator.
- The agent is a hand-written tool-use loop with hard limits in code.
- The queue is a Postgres table, not Kafka.
- Evaluation compares rules-only, LLM-only and the full agent, and adds injection and "should go to human" slices. False-repair rate is the headline metric.
- Added rules: hard-set independence, and the test split is run once.

## Cut (deferred, not abandoned)

Kafka, RAG and repair memory, the review screen, the Phase 3B message rebuild and CBPR+ validation layers, the Swift model and libpostal baselines, the Java LLM stage, Grafana, the demo page.

Cut order inside the week if time runs short: MCP server, then injection cases, then threshold polish. The verifier, the three-way table and the README are never cut.

## What the resume may honestly claim

- A Java/Spring Boot ingestion service (XML parsing, XSD validation) plus a Python repair agent, built on synthetic data.
- Measured results from `eval_runs` records, on the frozen test split and separately on the hand-written hard set, with N stated.
- Design claims that are true of the code: the model proposes and deterministic code verifies; limits are enforced in code; the model cannot approve or publish.

It may not claim: CBPR+ certification (say "implements a documented subset of CBPR+ address rules"), real bank or customer data, production use, or any number without an `eval_runs` record. GeoNames circularity means synthetic-split town and postcode accuracy is optimistic; say so beside the numbers.

## Swift timing

Swift has deferred Standards Release 2026 and expects to set new timing for structured addresses by December 2026. No cutover date is stated in this project; check Swift's announcement and date the check before publishing.
