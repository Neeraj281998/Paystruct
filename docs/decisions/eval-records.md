# Run records are the only source of numbers

Date: 2026-10-30. Status: accepted (Day 3).

## Decision

Every evaluation run writes one JSON file to `evals/results/`. These files are this project's equivalent of the `eval_runs` table in the original spec. A number may appear in the README or in a doc only if it comes from one of them. `docs/eval-results.md` is generated from them by `python -m evals.report` and is never edited by hand; `docs/decisions/hard-set-results.md` has a generated numeric section for the same reason.

A record holds: the git sha (and whether tracked files were modified), the split and its SHA-256, the number of records, the system, its config (model, prompt version and thresholds where they apply; `null` for rules-only), the seed, the UTC date, and every metric: exact match on all fields, field accuracy, precision/recall/F1 per element, auto-correct rate, false-repair rate with k/n, hallucinated values, route shares, latency p50 and p95, cost per 1,000, Wilson 95% intervals, and breakdowns by country, tier and tag (counts only for buckets under five records). Failure patterns are stored as counts, never as record ids.

**Per-record details (added after the first real agent run).** For `dev` and `calibration` a record also keeps, for every record, the input, gold, output, route, which fields matched, were wrong, missing or extra, hallucinated elements, latency, cost and the system's own report (for the agent: the rules' output and how each field was set, every attempt's proposal with the verifier's reasons and confidence, and every model call and tool call with token counts). This is what makes a failure diagnosable. For `hard` and `test` no per-record details are written, so nobody reads individual failures there. `--ids a,b,c` re-runs chosen records of a split (for example a few failures, for a few cents); the record is marked with a `subset` and the report shows it as its own table.

## Why

- A number in a doc that cannot be traced to a run drifts, and this project's whole claim is that nothing is invented.
- The false-repair rate (ACCEPT with any wrong field, out of all ACCEPT records) is the most important metric, so its k/n is stored and printed beside every percentage.
- The scorer is `agent/rules/scoring.py`, used as it is (labelling guide section 10), so every system is scored the same way.

## Guards

- `dev` and `calibration` run freely. `hard` runs only with `--split hard`, for reporting; the engine is never changed because of it without an entry in `docs/results-changelog.md`.
- `test` is refused without `--final`. With `--final` it runs only if `TEST_RUN_ENABLED` in `evals/guards.py` is True (it was set in its own commit, e7d2f7f, before the `final-config` tag) and the frozen hash is intact (`verify_frozen`), and a warning is printed. The test split was run once, for the final numbers; tests never read the real file.
- The plan's `agent/eval/` is `evals/` in practice.

## Not yet

`llm_only` and `agent` are stubs that print "not yet available". They write no record, and the report shows "not run yet" for them.

## Development-only sources

`--source robustness` runs the 30 audit addresses (`agent/audit/robustness_cases.py`), scored against the author's own expectations. The run record has `split: robustness` and `development_only: true`, keeps per-record details, and is **excluded from `docs/eval-results.md`** (the report skips it and says so). It is not a result.
