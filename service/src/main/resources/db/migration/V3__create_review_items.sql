CREATE TABLE review_items (
  address_id    UUID PRIMARY KEY REFERENCES addresses(id),
  status        TEXT NOT NULL,              -- PENDING, APPROVED, CORRECTED
  corrected     JSONB,
  reviewed_at   TIMESTAMPTZ
);
