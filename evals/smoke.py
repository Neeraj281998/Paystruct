"""CI smoke run: rules only, no LLM, no secrets, no GeoNames file, on a fixed 100-record sample of dev.

python -m evals.smoke            # compare with evals/smoke_baseline.json, fail if exact_all drops by more than 2 points
python -m evals.smoke --write    # (re)write the baseline, deliberately
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evals import guards
from evals.metrics import compute
from evals.run import run_system
from evals.systems import RulesOnly

HERE = Path(__file__).resolve().parent
IDS = HERE / "smoke_ids.json"
BASELINE = HERE / "smoke_baseline.json"
MAX_DROP_POINTS = 2.0


def sample(records: list[dict]) -> list[dict]:
    ids = set(json.loads(IDS.read_text()))
    chosen = [r for r in records if r["id"] in ids]
    if len(chosen) != len(ids):
        raise SystemExit(f"smoke sample: expected {len(ids)} dev records, found {len(chosen)}")
    return chosen


def measure() -> dict:
    records = sample(guards.load_records(guards.check_split("dev")))
    m = compute(run_system(RulesOnly(use_gazetteer=False), records))
    return {"n": m["n"], "exact_all_k": m["exact_all"]["k"], "exact_all_pct": round(100 * m["exact_all"]["k"] / m["n"], 2),
            "false_repair_k": m["false_repair"]["k"], "false_repair_n": m["false_repair"]["n"], "gazetteer": "none"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    now = measure()
    print(f"smoke (rules only, no gazetteer, {now['n']} dev records): exact_all={now['exact_all_k']}/{now['n']} ({now['exact_all_pct']}%), "
          f"false repair {now['false_repair_k']}/{now['false_repair_n']}")
    if args.write:
        BASELINE.write_text(json.dumps(now, indent=2) + "\n")
        print(f"wrote {BASELINE}")
        return 0
    base = json.loads(BASELINE.read_text())
    drop = base["exact_all_pct"] - now["exact_all_pct"]
    if drop > MAX_DROP_POINTS:
        print(f"FAIL: exact_all dropped by {drop:.2f} points against the baseline ({base['exact_all_pct']}%); the limit is {MAX_DROP_POINTS}")
        return 1
    print(f"OK: within {MAX_DROP_POINTS} points of the baseline ({base['exact_all_pct']}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
