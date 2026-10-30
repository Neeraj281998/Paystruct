-- Agent tables. Idempotent: safe to apply any number of times. The Java service's Flyway tables are not touched.
CREATE TABLE IF NOT EXISTS agent_repairs (
    msg_id        text PRIMARY KEY,
    status        text NOT NULL,                 -- in_progress | repaired | review | retry_later
    original_lines jsonb NOT NULL,
    repaired      jsonb,                         -- the accepted address (structured fields, optional AdrLine)
    route         text,                          -- REPAIRED | REVIEW
    confidence    numeric,
    attempts      integer NOT NULL DEFAULT 0,
    cost_usd      numeric NOT NULL DEFAULT 0,
    api_failures  integer NOT NULL DEFAULT 0,
    reasons       jsonb,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_steps (
    id          bigserial PRIMARY KEY,
    msg_id      text NOT NULL REFERENCES agent_repairs (msg_id),
    attempt     integer NOT NULL,
    step        integer NOT NULL,
    tool        text NOT NULL,
    input       jsonb,
    output      jsonb,
    tokens_in   integer NOT NULL DEFAULT 0,
    tokens_out  integer NOT NULL DEFAULT 0,
    latency_ms  integer NOT NULL DEFAULT 0,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS agent_steps_msg_id_idx ON agent_steps (msg_id);

-- A table of queued items for the worker (synthetic data only).
CREATE TABLE IF NOT EXISTS agent_queue (
    msg_id        text PRIMARY KEY,
    raw_lines     jsonb NOT NULL,
    country_hint  text,
    enqueued_at   timestamptz NOT NULL DEFAULT now()
);
