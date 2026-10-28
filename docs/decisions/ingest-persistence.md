# Where ingestion results are stored

Status: accepted (Phase 1)

## Context

Phase 1 must store each message under its SHA-256 and, for a repeated message, return the stored result. The four spec tables (`messages`, `addresses`, `review_items`, `eval_runs`) were created exactly as written, but they have no place for the XSD errors found at ingestion, nor for an address's `xmlPath`, country hint, already-structured flag or the structured fields it arrived with.

## Decision

- `messages`, `addresses`, `review_items`, `eval_runs`: exactly the spec columns. No columns added. `rule_cards` is left for Phase 7.
- Per-address ingestion facts go in `addresses.evidence` under an `ingest` key: `ordinal` (document order, used for stable output), `xmlPath`, `countryHint`, `alreadyStructured`, `existing`. `result` and `method` stay empty until a later phase fills them. Later phases should merge into `evidence`, not replace it.
- Schema errors go in one new table, `message_ingest_reports` (`message_id`, `schema_error_count`, `schema_errors` JSONB), migration `V5`. This is the one addition to the spec's data model. It is a separate table so the spec tables stay as written.
- `messages.status` is `RECEIVED` after ingestion. `input_valid` is false when any schema error was found.
- Insert uses `ON CONFLICT (content_hash) DO NOTHING`, so two simultaneous uploads of the same content cannot both win; the loser returns the stored result with `duplicate: true`. Message, report and addresses are written in one transaction.

## Consequences

- A duplicate returns the stored job ids, order and schema errors, not a recomputation.
- If the data model is later revised, `message_ingest_reports` is the thing to fold in.
