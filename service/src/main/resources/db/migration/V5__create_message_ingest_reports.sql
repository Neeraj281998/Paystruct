-- Not in the spec's data model: the four spec tables have nowhere to keep the XSD errors found at ingestion,
-- and a duplicate message must return the stored result. See docs/decisions/ingest-persistence.md.
CREATE TABLE message_ingest_reports (
  message_id         UUID PRIMARY KEY REFERENCES messages(id),
  schema_error_count INTEGER NOT NULL,
  schema_errors      JSONB NOT NULL
);
