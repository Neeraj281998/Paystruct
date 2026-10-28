CREATE TABLE messages (
  id            UUID PRIMARY KEY,
  content_hash  CHAR(64) UNIQUE NOT NULL,   -- idempotency
  message_type  TEXT NOT NULL,
  status        TEXT NOT NULL,              -- RECEIVED, PROCESSING, DONE, NEEDS_REVIEW
  input_valid   BOOLEAN,
  received_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
