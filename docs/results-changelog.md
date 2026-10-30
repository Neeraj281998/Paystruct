# Results changelog

Every change to the engine (`agent/rules/`), the prompts or the thresholds that is made after seeing hard-set results is logged here, with the reason, so that a later improvement on the hard set can be read for what it is.

Rule: the hard set is for reporting. Nothing under `agent/rules/` is changed because of what a hard-set run shows unless it is logged below first.

| date | change | reason (what the hard-set run showed) | files | git sha |
|---|---|---|---|---|

(empty: no engine change has been made after seeing hard-set results)

## Presentation and wording changes after the final runs (no result changed)

Made on 2026-10-30, after the final runs and the `final-config` tag. Nothing under `agent/`, no scoring, metrics or threshold code, no run record and no
tag was touched; no evaluation was re-run.

| change | reason | files |
|---|---|---|
| The per-element, by-country, by-tier, by-tag and failure-pattern tables are labelled "rules-only run", with a one-line note | those tables come from the rules-only record; the headline table above them mixes three systems and the labels were missing | `evals/report.py`, `docs/eval-results.md` |
| `evals/report.py --readme` and `--resume-numbers` generate the README results block and `docs/resume-numbers.md` from the same records | so no number in the README or resume notes is typed by hand | `evals/report.py` |
| Stale wording fixed: the test guard "is refused until the flag is set" | the flag was set in e7d2f7f and the test split was run once | `docs/decisions/eval-records.md`, `docs/decisions/final-run-protocol.md`, `scripts/final_run.py` (comments and message text only) |

The headline system rows of `docs/eval-results.md` are byte-identical before and after the regeneration.
