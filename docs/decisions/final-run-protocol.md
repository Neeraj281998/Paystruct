# Final-run protocol

Date: 2026-10-30. Status: accepted. Script: `scripts/final_run.py`.

## What is frozen, and how

Code, prompts, model id and thresholds are frozen by the git tag **`final-config`**. The tag marks the commit that is run. Before the tag:

1. Everything is developed and tuned on dev and calibration only. The threshold is set on calibration (`python -m evals.calibrate --apply`, `docs/decisions/threshold.md`).
2. The test guard is enabled by a separate commit by the project owner (`TEST_RUN_ENABLED` in `evals/guards.py`). It is not enabled by anything in this repository's code or scripts.
3. The tag is created on that commit: `git tag final-config`.

`scripts/final_run.py` refuses to start unless the working tree is clean, `final-config` exists **and is on HEAD**, `scripts/verify_frozen.py` passes, and `PAYSTRUCT_RUN_BUDGET_USD` is set. It prints the estimate for every run, requires typing `FINAL`, and runs in order: all three systems (`rules_only`, `llm_only`, `agent`) on the hard set; all three on the test split with `--final`; the injection slice for any system that has not run it; then it regenerates `docs/eval-results.md` and the hard-set note. It stops at the first failing step.

## The rules of the final run

- **Once.** The hard set and the test split are run once, for all three systems, with the frozen configuration. The test split is never used to tune anything, and the hard set is read only through the harness, for reporting.
- **Any change after seeing the results is logged** in `docs/results-changelog.md` with the reason, **and both results are reported** (the first and the changed). A change to code, prompts, model id or thresholds after the final run makes the earlier result the "first result" and the later one the "changed result"; neither is deleted.
- **Single run.** The model's temperature cannot be set, so every model result is from a single run and can vary slightly. It is not averaged and not re-rolled until it looks better.
- **No per-record details** are stored for the hard set or the test split (counts only), so individual failures there are not read.

## The headline table

Each system in its own row, from the run records only (`docs/eval-results.md`, generated):

- auto-correct rate (ACCEPT and exactly right, out of all records);
- **false-repair rate** with k/n and its Wilson 95% interval (ACCEPT with any wrong field, out of all ACCEPT records);
- hallucinated values;
- ACCEPT / NEEDS_LLM / REVIEW shares;
- REVIEW cases with a correct proposal;
- cost per 1,000 and p50 / p95 latency.

`exact_all` and field accuracy are shown only inside a single system's own section, because the systems define them differently (`llm-only-baseline.md`). Dev and calibration are optimistic (shared GeoNames, tuned on); the hard set is small and AI-drafted; the injection slice is AI-written (N=15), development-only, and reported in its own section with its first and final results.

## What the final result does and does not show

It shows how each system behaves on 1,000 more synthetic records of the same generator and on 40 AI-drafted addresses, under one configuration. It does not show behaviour on real payment data, and nothing here claims CBPR+ certification (the project implements a documented subset of CBPR+ address rules).
