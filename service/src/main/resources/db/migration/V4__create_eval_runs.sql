CREATE TABLE eval_runs (
  id            UUID PRIMARY KEY,
  git_sha       TEXT NOT NULL,
  config        JSONB NOT NULL,             -- model, prompt version, thresholds
  metrics       JSONB NOT NULL,
  ran_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
