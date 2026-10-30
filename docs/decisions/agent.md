# The repair agent: propose, then verify (Day 4)

Date: 2026-10-30. Status: accepted. Code: `agent/repair/`. Config: `agent/config/routing.yml`, `agent/config/prices.yml`. Schema: `agent/db/schema.sql`.

## Principle

The AI proposes, plain code decides. The model has four tools (`parse_address`, `country_lookup`, `validate_candidate`, `submit_repair`) and none of them approves, publishes or writes to a queue. `submit_repair` only hands a proposal to code. Every route is chosen by `agent/repair/pipeline.py`.

## Flow

1. The rules engine runs first (`agent/rules`).
2. **Rules ACCEPT:** no model call. The output still goes through the validator and the grounding check; a failure goes to REVIEW.
3. **Rules REVIEW** (no town written, contradiction, no country): not sent to the model. A model cannot supply a town that is not written, and a contradiction is a human's call.
4. **Rules NEEDS_LLM:** the agent proposes. A proposal is accepted only if the validator and the grounding check pass and every field has support. Otherwise the reason codes go back to the agent, up to 3 attempts, then REVIEW.
5. **Routing:** valid, grounded, supported and confidence at or above the threshold goes to REPAIRED; everything else goes to REVIEW. The threshold (0.85) is a placeholder in `routing.yml`, set on the calibration split on Day 5.

## The checks (all deterministic, all in code)

- **Validator** (`validator.py`, pure): ADDR_UNSTRUCTURED, MISSING_TWNNM, MISSING_CTRY, INVALID_CTRY (ISO 3166-1 alpha-2 table), FIELD_TOO_LONG (limits read from the XSD), POSTCODE_FORMAT (country profile regex), HYBRID_LINES_EXCEEDED and HYBRID_DUPLICATION. The AdrLine maximum is the existing `max_adr_lines` value in `agent/rules/config.yaml`, a placeholder: **the real CBPR+ limit must be confirmed** (`hybrid-address.md`). An address with no written town is not special-cased: TwnNm is absent, the validator says MISSING_TWNNM, and the route is REVIEW.
- **Grounding** (`grounding.py`): every value must occur in the original lines (case, whitespace and the allowed punctuation normalised; an allowlisted abbreviation expansion is equal). Ctry must be derivable from the text (a written country name or code, the message's country hint, or a postcode pattern unique to that country), otherwise UNGROUNDED_COUNTRY. **Agreement:** a field the rules set with explicit evidence must not be contradicted. **Consistency:** a written town must be in the gazetteer for that country; with no gazetteer the check is skipped, the result is marked unchecked, and confidence goes down.
- **Support** (`support.py`): the same standard the rules use. A value is *explicit* when a postcode pattern, a keyword pattern, a word list of the country profile or the gazetteer recognises it; otherwise it is *elimination*.
- **Citation guard:** `evidence_rules` in `submit_repair` must be rule ids that `parse_address` returned in this attempt (the pre-run parse shown to the model counts). A schema-invalid or badly cited submission is a failed attempt.

## Why elimination fields cannot be auto-accepted

A value that nothing recognises (a locality that is not a place, a street name with no street word, "Mulberry Hall" with no building word) can only be right because it is what is left over. The rules therefore never accept such a field (Day 2, confidence by evidence), and the model gets no exemption: if the model proposes a grounded value that has no support, confidence is capped at 0.60, below the threshold, so the address goes to REVIEW (after feedback, the model may leave the value out or use a hybrid address). Grounding alone cannot do this job, because grounding only says the text is in the input, not that it is in the right field. The cost is a higher human-review rate; the gain is that a plausible guess is never published.

## Why the model is skipped for rules ACCEPT and rules REVIEW

ACCEPT: every field already has explicit evidence, so a model call adds cost and a new way to be wrong (a model "improving" a correct address) and nothing else. REVIEW: the reasons are things a model must not decide (invent a town, pick a country when texts disagree). Skipping the model is also the cheapest and fastest path, and it keeps the number of model-exposed payments small.

## Why our own loop

About 100 lines of code that enforce the limits where they cannot be argued with: at most 8 tool calls per attempt, at most 3 attempts per payment, a per-payment cost budget (`MAX_COST_USD_PER_PAYMENT`, default 0.05), a request timeout, and bounded retries with backoff. A framework would hide the exact point where a limit is checked and would add dependencies; the tool-use protocol is small. Cost comes from the API's token usage times `agent/config/prices.yml`. A persistent API failure leaves the payment `retry_later`, and after 3 tries it goes to REVIEW.

## Model and API choices (checked 2026-10-30)

- **Model:** `claude-haiku-5-5`, the current Haiku, from the model overview at platform.claude.com (docs.claude.com redirects there), "From $0.10 / input MTok, From $0.50 / output MTok", checked 2026-10-30. Override with `PAYSTRUCT_MODEL`; a model without a price in `prices.yml` is a configuration error.
- **No temperature.** The brief asked for temperature 0. Claude Haiku 5.5 returns a 400 for any non-default `temperature`, `top_p` or `top_k`, and the Python SDK (2.3.0) no longer accepts `temperature` on `messages.create` at all. Determinism here comes from the verifier, not from sampling: whatever the model says, the same input gets the same checks. `output_config.effort` is `low`.
- **Thinking** is left at its default (adaptive); thinking blocks are passed back unchanged with the tool results, as the API requires.
- **Sampling-free, tool_choice `auto`:** the model is asked in the prompt to call `submit_repair` once.

## Persistence and idempotency

Tables `agent_repairs` (msg_id primary key) and `agent_steps`, plus `agent_queue`, in the existing PostgreSQL, created by `agent/db/schema.sql` (`CREATE ... IF NOT EXISTS`, applied with `python -m agent.db`). The Java Flyway tables are untouched. The worker claims a msg_id by inserting it as `in_progress`; a conflict means it is already handled and is skipped. A `retry_later` payment can be claimed again until 3 tries; an `in_progress` claim older than the lease (a crashed worker) can be taken over. The result and the steps are written in one transaction.

## Real API runs

`--limit N` is mandatory; `PAYSTRUCT_RUN_BUDGET_USD` (default 2.00) aborts a run; an estimate is printed first and more than 50 records need `--yes`; more than 30 need `--approved-over-30` (a rule for the session in which this was built). The agent runs on dev only until Day 5. The key is read from `ANTHROPIC_API_KEY` in the environment by the SDK; this code never reads, stores or logs it.

## Honest limits

- No real API call was made when this was built (no key in the environment), so no number about the model's behaviour exists yet; everything above is tested with a scripted fake model and with the real SDK objects over a mock transport.
- The rules ACCEPT path can still produce a wrong fix when the text is real but in the wrong field. See `docs/threat-model.md`.
- An address that hybridises (TwnNm, Ctry and AdrLine) is valid but is not equal to a structured gold record, so the evaluation counts it as wrong; it is a safety valve, not a goal.
