# Progress

- [x] Phase 0: setup
- [x] Phase 1: foundations and ingestion
- [x] Phase 2: synthetic data (2A and 2B done; the hand-written hard set is still to be written by the owner)
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

## Phase 2A notes

Built: `data/labelling-guide.md` (decisions applied, awaiting approval) and the IE/GB reverse generator in `data/generator/` with tests (`python -m pytest`), the project seed in `data/generator/SEED`, and `docs/decisions/synthetic-generator.md`.

Not built: the other six countries, the four splits, the frozen test split, the hard-set tooling, the message builder and the stats script (all Phase 2B).

Things to know:
- Typos in gold stay as written, abbreviations are not expanded in gold, and the scorer folds the allowlisted expansions (guide sections 9 and 10).

## Phase 2B notes

Built: generators for FR, DE, NL, CA, US and IN (labelling guide sections 12-18); the dev (600), calibration (400) and test (1,000) splits in `data/splits/` with `splits.manifest.json`; the frozen test hash (`test.sha256`) and `scripts/verify_frozen.py`; `scripts/check_splits.py`; the hard-set scaffold (`data/hard_set/*.yaml`, validator, converter to `hard.jsonl`); the message builder and 300 sample messages in `data/messages/` with `manifest.json`; `scripts/split_stats.py`. 341 generator tests (`python -m pytest` in `data/generator`).

Not built, by design: the 100 hand-written hard-set addresses (the owner writes them), rules, evaluation harness, scorer, baselines.

Things to know:
- `data/splits/hard.jsonl` is empty. Each country file holds two entries marked EXAMPLE, which are left out unless `--include-examples`. `build_hard_set.py` refuses fewer than 100 entries without `--allow-partial`.
- The disjointness check does not open `test.jsonl`; it uses address-key hashes recorded when the splits were built (see `docs/decisions/splits-and-messages.md`). `--include-test-file` is there for the owner.
- 25 of the 300 messages are XSD-invalid on purpose (`too_many_lines` fault); `manifest.json` says which.
- Calibration and test tiers are balanced to within one record per country, not exactly equal (400 and 1,000 do not divide by 3).
- New pinned dependencies: `lxml`, `PyYAML`.

## Phase 2B follow-up: postcode-to-town ties (2026-10-29)

Checked every postcode-to-town table against the GeoNames files. Found wrong ties in US (13 of 41 pairings contradicted), DE and IN, and a locality-to-outward-code gap in GB. Fixed: US, DE and IN now write only postcodes GeoNames lists for the town (100% confirmed); IN sectors and localities and GB localities use their own codes where GeoNames gives them; NL Amsterdam stops at 1098. dev, calibration, test and the sample messages were regenerated and the test split was re-frozen once, with the owner's approval (new `test.sha256`, `test.jsonl` not opened).

Decision records: `postcode-ties.md` (lists every pairing GeoNames does not confirm), `geonames-circularity.md`, and the re-freeze entry in `splits-and-messages.md`. Labelling guide section 19 awaits approval.

Things to know:
- The generator and the Phase 3 rules engine will both use GeoNames, so town and postcode accuracy on synthetic data is optimistic; the hand-written hard set is the independent check and must be reported beside it.
- The test split must not be regenerated again without the owner's explicit approval.

