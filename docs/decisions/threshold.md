# Repair threshold

The REPAIRED threshold in `agent/config/routing.yml` is chosen on the calibration split by `python -m evals.calibrate`: the point with the most ACCEPT coverage whose observed false-repair rate among the accepted is at most 1%.

**Caveat.** The calibration split was already used for reporting (the Day 2 audit and the Day 3 baseline) and its failure patterns informed earlier fixes, so the threshold chosen on it is slightly optimistic. The interval below is the honest statement of how little a few hundred records can show.

## 2026-10-30: threshold 0.94

- Reason: the point with the most ACCEPT coverage (86.2% of 400 calibration records) whose observed false-repair rate among the accepted is at most 1% (2 wrong of 345 accepted = 0.58%; Wilson 95% interval 0.2% to 2.1%).
- Run record: `20261030T145505Z_agent_calibration_fe7054e.json`.
- Applied with `python -m evals.calibrate --apply`; not applied automatically.

## What the calibration could and could not show

The calibration data was largely uninformative. About 99 percent of the accepted calibration records are rules ACCEPTs that the model never saw (344 of the 345 accepted in `20261030T145505Z_agent_calibration_fe7054e.json`), and the confidence formula gives all of them the same score (0.94: the base, the full agreement with the rules, the gazetteer signal). A threshold swept from 0.50 to 0.99 therefore does little until it reaches 0.94, and above it accepts almost nothing: **the chosen threshold sits at the plateau of that single confidence value, so it was fixed by the formula's constants and not by the data.** It is still the right place for a safety-first threshold (it accepts every rules ACCEPT and nothing less sure), but it should not be read as a measured optimum.

**Consequence for retries.** The attempt penalty (0.04 per attempt after the first) lowers a model fix's score below the plateau. At this threshold a model fix that is valid, grounded and correct only on attempt 2 cannot be auto-repaired: it goes to REVIEW with its proposal kept for the person (`LOW_CONFIDENCE`). Retries therefore improve the proposals a person sees, but they do not add auto-repairs. This is a deliberate, safety-first consequence, written down so nobody mistakes it for a bug. It is documented by a test (`test_with_the_applied_threshold_a_fix_correct_only_on_attempt_2_goes_to_review_...`), which will fail if a recalibration moves the threshold so that the statement is no longer true.

**The signal constants are frozen** (`agent/config/routing.yml`): the threshold was calibrated against the confidence they produce, so changing any of them invalidates it.
