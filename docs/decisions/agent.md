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

## First real run on dev (2026-10-30)

Run record `evals/results/20261030T135058Z_agent_dev_first30_98af5d2.json`: the first 30 dev records, model `claude-haiku-5-5`. The agent got exact_all 26/30 and a false-repair rate of 4/30 (every record was routed ACCEPT, so 4 of 30 accepted records were wrong); rules-only got 30/30 exact on the same records, with 4 of them routed NEEDS_LLM. Cost $0.008 for the run (about $0.27 per 1,000 records), latency p50 4 ms (the 26 rules-only records) and p95 8.3 s (the model).

### What the evidence says

That run record did not keep per-record details, so the four wrong records were reconstructed with no API call (`python -m agent.audit.first_run_diagnosis`, dev only):

- The run's only failure pattern is `TwnLctnNm:missing`, four times. Every other field of every record matches gold and no extra field was output.
- The four records the model saw are exactly the four that the rules route to NEEDS_LLM among the first 30 (the other 26 are rules ACCEPT, which never call the model and were exact). The four are `in-00001`, `in-00002`, `ie-00003` and `in-00003`.
- In all four the rules' output is **exactly gold**, including `TwnLctnNm` (Velachery, Vastrapur, Ballywaltrim, Gachibowli). The rules routed them NEEDS_LLM only because the locality was set by elimination: the place is not in the gazetteer and no pattern recognises it.
- The verifier on the rules' own output says: no hard reason, **unsupported: TwnLctnNm**, so confidence is capped at 0.60 and the route is REVIEW. The same output with the locality removed says: valid, grounded, supported, confidence 0.964 on the first attempt (0.924 on the second), so REPAIRED.

So a model that keeps the correct locality is rejected, and a model that drops it is accepted at 0.92 to 0.96. The model's own output could not be inspected; this is an inference from the failure pattern and the code path (an accepted output cannot contain an unsupported locality, so the locality was absent from the accepted proposal), and the next run, which keeps per-record details, will show the proposals attempt by attempt. The run cost ($0.002 per payment, about four calls) fits two attempts: the first keeping the locality, the second dropping it after the feedback.

### Classification

| category | count | evidence |
|---|---|---|
| (a) label convention missing from the prompt | 0 | no field differs in value; nothing was expanded, re-cased or renamed |
| (b) the model changed or removed a field the rules had set correctly | **4** | `TwnLctnNm` present and exact in the rules' output, absent in the accepted output |
| (c) real text in the wrong field, which grounding cannot catch | 0 | no field holds a value that differs from gold |
| (d) scoring or adapter bug | 0 | the pattern is `missing`, not `wrong` or `extra`; and an accepted output cannot contain the unsupported locality (it would have been capped to REVIEW), so a dropped field cannot be an adapter loss of a field the model sent |

Note that the removed field was set by *elimination*, not by explicit evidence, so the agreement check (which protects explicit fields only) did not apply. That is the gap.

### Root cause

The verifier checks that what is there is valid, grounded and supported. It never checks that nothing was lost. Dropping text is always valid, always grounded and always supported. Two other pieces then make dropping the only way to a repair: the support cap (an unsupported field can never reach REPAIRED) and the feedback text ("fix the problems, or leave the offending parts out"), which invites the deletion. The confidence formula does not notice either: it averages over the fields that remain.

A second finding about dev as a test: the full-dev rules-only record shows 74 of 600 records routed NEEDS_LLM and every one of the 600 exact. On dev, then, the rules' output for every record the model sees is already gold, so the model can only keep dev exact or make it worse. Dev cannot show the model helping. That has to come from calibration (Day 5), from the hard set, or from deliberately damaged inputs.

### Proposed fixes, ranked (not applied; waiting for approval)

1. **A completeness check in the verifier (root-cause fix).** Every input token that is not the country text must appear in the candidate, in a field or in `AdrLine`; otherwise a hard reason `DROPS_TEXT` (with the missing text) goes back to the model. With the feedback fixed (next item) the four records would end as REVIEW, which is the honest answer.
2. **Change the feedback.** Replace "or leave the offending parts out" with "keep the text: move it to AdrLine, or leave the address for review". Same change, tiny, no extra cost.
3. **Decide what a hybrid result is.** If dropped text may be moved to `AdrLine`, a hybrid becomes the way out for unsupported fields. A hybrid is valid but never equals structured gold, so counting it as an automatic repair would make the false-repair rate worse. My recommendation: a hybrid proposal goes to REVIEW (it is the system saying it could not structure the address), or gets its own route that is reported separately. Your call.
4. **Lock the rules' fields.** The model may not change or delete a field the rules set with explicit evidence (extend the agreement check from six fields to all explicit ones), and may change an elimination field only to another value or to the same text moved to AdrLine, never delete it. It overlaps with 1 but makes the model's job explicit.
5. **Do not call the model when it cannot add evidence.** If the only reasons the rules gave are `by_elimination:*` and the model has no tool that can supply independent evidence (a locality gazetteer would be one), send the address to REVIEW directly. This saves the cost and removes the regression. It is the cheapest rule, but it only helps this class.
6. **Show the model `how_set` and tell it to fill only unresolved fields.** A prompt change; useful for cost and clarity, not a safety measure by itself, because only items 1 and 4 are enforced by code.
7. **Labelling-guide conventions in the system prompt.** Not implicated in these four failures. Worth testing later on calibration, where Room keywords and "text as written" may matter.
8. **Lower the model's contribution to confidence.** It is already ±0.03 around 0.5 and was not the cause (the model said 0.9, the score would have passed at 0.5 too). No change.

I think the root cause is item 1's gap: **a repair that loses information is treated as a valid repair**. Items 1 and 2 together fix it; item 5 removes the avoidable model calls; item 3 is a decision about what the product promises. After approval I will write the tests from these descriptions first (a scripted model that drops a correct elimination field must end in REVIEW), then change the code, and re-run only these four ids with `python -m evals.run --system agent --split dev --ids in-00001,in-00002,ie-00003,in-00003` (a few cents).
