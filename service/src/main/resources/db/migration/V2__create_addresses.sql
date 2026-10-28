CREATE TABLE addresses (
  id            UUID PRIMARY KEY,
  message_id    UUID REFERENCES messages(id),
  party_role    TEXT NOT NULL,
  raw_lines     JSONB NOT NULL,
  result        JSONB,                      -- structured fields
  evidence      JSONB,                      -- which rule or model set each field
  method        TEXT,                       -- RULES, LLM, REVIEW
  confidence    NUMERIC(4,3),
  latency_ms    INTEGER,
  llm_cost_usd  NUMERIC(10,6)
);
