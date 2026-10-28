# PayStruct

## Summary

1. PayStruct converts free-text postal addresses in ISO 20022 payment messages (pacs.008 and pain.001) into structured `PstlAdr` elements.
2. Deterministic rules run first; an LLM fills only what the rules cannot resolve.
3. Every LLM answer must pass grounding, schema, consistency and agreement checks, so no value is ever invented.
4. Low-confidence or contradictory results go to a human review queue, and validation failures are explained with a cited rule (RAG over rule cards).
5. A public evaluation harness compares five systems, including libpostal and Swift's open-source model, on a frozen synthetic test set.

## Tech stack

| Layer | Choice |
|---|---|
| Service | Java 21, Spring Boot 3 |
| Messaging | Apache Kafka (KRaft), Spring Kafka |
| XML | JAXB with `xjc`, StAX, `javax.xml.validation` |
| Database | PostgreSQL 16 with pgvector |
| Cache | Redis |
| LLM | Anthropic API (Claude) |
| Gazetteer | GeoNames city data |
| Baselines | libpostal, Swift's open-source model |
| Data and evaluation | Python 3.12, Faker, pandas |
| Testing | JUnit 5, jqwik, Testcontainers |
| Observability | Micrometer, Prometheus, Grafana |
| CI | GitHub Actions |
| Local stack | Docker Compose |
| Optional stretch | Terraform for AWS |

## Repository layout

```
paystruct/
  README.md                 results table, architecture, how to run
  docker-compose.yml        Kafka, Postgres, Redis, Prometheus, Grafana
  service/                  Spring Boot application
    src/main/java/.../ingest/     parsing, validation, address jobs
    src/main/java/.../rules/      AddressRule chain and ParseState
    src/main/java/.../llm/        fallback, checks, confidence
    src/main/java/.../explain/    rule-card retrieval and explanations
    src/main/java/.../pipeline/   Kafka consumers and assembler
    src/main/java/.../api/        REST controllers
    src/main/resources/countries/ one YAML profile per country
    src/main/resources/xsd/       downloaded ISO 20022 schemas
  rule-cards/               one YAML file per rule
  data/
    generator/              Python synthetic data generator
    labelling-guide.md      how ambiguous cases are labelled
    splits/                 dev, calibration, test (frozen), hard set
  eval/                     Python harness, baselines, reports
  review-ui/                review screen and demo page
  docs/
    architecture.md
    decisions/              one short record per design decision
```

## Working rules

- Build only the phase I ask for. Never build ahead.
- All data is synthetic. Never add real customer, bank or employer data.
- The frozen test split (`data/splits/test.jsonl`) is never read while tuning rules, prompts or thresholds. Thresholds are set on the calibration split only.
- No number appears in the README or docs unless it comes from an `eval_runs` record.
- Secrets live in environment variables only. Never write them to files or commit them.
- Ask me before downloading any file or adding a large dependency.
- Never claim CBPR+ certification. Say: implements a documented subset of CBPR+ address rules.
- Every rule and every check gets a unit test.
- At the end of each phase: summarise what was built, list the exact commands to run and test it, update `docs/PROGRESS.md`, and add a short decision record in `docs/decisions/` for each real design choice.

## Detail

The full specification is in `docs/spec.md`. Read the relevant section there before starting a phase. Progress is tracked in `docs/PROGRESS.md`.
