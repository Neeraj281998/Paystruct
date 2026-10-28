# Progress

- [x] Phase 0: setup
- [x] Phase 1: foundations and ingestion
- [ ] Phase 2: synthetic data
- [ ] Phase 3: rules engine
- [ ] Phase 4: evaluation harness and baselines
- [ ] Phase 5: LLM fallback
- [ ] Phase 6: review queue and API and UI
- [ ] Phase 7: RAG explanations
- [ ] Phase 8: Kafka pipeline
- [ ] Phase 9: final evaluation and publish

## Phase 1 notes

Built: repository layout, Docker Compose (PostgreSQL 16 with pgvector, Redis), Spring Boot 3 service on Java 21 (Maven wrapper), Flyway migrations, JAXB classes generated from the two XSDs, safe StAX ingestion, message-type detection from config, XSD validation, address job extraction, SHA-256 deduplication, `POST /v1/messages` and `GET /v1/messages/{id}`.

Not built, by design: rules engine, LLM, Kafka, RAG, `rule_cards` table, the other endpoints.

Decision records: `docs/decisions/` (`xsd-versions`, `maven-build`, `safe-xml-parsing`, `ingest-persistence`, `address-job-extraction`).

Things to know:
- The supplied XSDs use `PostalAddress27`, not the `PostalAddress24` in the spec; several maximum lengths differ. `docs/spec.md` is unchanged; `xsd-versions.md` lists the differences and the XSD is the source of truth from now on.
- One table was added beyond the spec's data model (`message_ingest_reports`), see `ingest-persistence.md`.
