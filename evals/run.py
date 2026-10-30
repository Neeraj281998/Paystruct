"""python -m evals.run --system rules_only --split dev

Runs one system over one split and writes a run record to evals/results/. The run records are the only source of numbers
for the README and the docs (docs/decisions/eval-records.md).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from evals import guards
from evals.metrics import compute, evaluate_record
from evals.systems import SYSTEMS, NotAvailable

RESULTS_DIR = guards.REPO_ROOT / "evals" / "results"


def git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=guards.REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def run_system(system, records: list[dict], budget_usd: float | None = None, log=print) -> list:
    """Run every record; stop early when the run budget is reached (the records not run are not counted)."""
    evals = []
    spent = 0.0
    for rec in records:
        if budget_usd is not None and spent >= budget_usd:
            log(f"run budget of ${budget_usd:.2f} reached after {len(evals)} records: stopping")
            break
        out = system.run(rec["raw_lines"], rec.get("country_hint"))
        spent += out.cost_usd
        evals.append(evaluate_record(rec, out))
    return evals


def build_record(system, split: str, records: list[dict], evals: list, seed: int = 0, split_sha: str = "", limit: int | None = None) -> dict:
    return {
        "git_sha": git("rev-parse", "HEAD"),
        "git_dirty": bool(git("status", "--porcelain", "--untracked-files=no")),
        "date": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "system": system.name,
        "split": split,
        "n_records": len(evals),
        "limit": limit,
        "aborted_by_budget": len(evals) < len(records),
        "split_sha256": split_sha,
        "seed": seed,
        "config": system.config(),
        "metrics": compute(evals),
    }


def write_record(record: dict, out_dir: Path = RESULTS_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = record["date"].replace(":", "").replace("-", "")
    tag = f"_first{record['limit']}" if record.get("limit") else ""
    path = out_dir / f"{stamp}_{record['system']}_{record['split']}{tag}_{record['git_sha'][:7]}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--system", required=True, choices=sorted(SYSTEMS))
    ap.add_argument("--split", required=True)
    ap.add_argument("--final", action="store_true", help="required for the test split (refused in this session)")
    ap.add_argument("--no-gazetteer", action="store_true", help="rules_only without the GeoNames file (what CI can run)")
    ap.add_argument("--limit", type=int, help="run only the first N records of the split (mandatory for the agent)")
    ap.add_argument("--yes", action="store_true", help="required for the agent on more than 50 records, after reading the estimate")
    ap.add_argument("--approved-over-30", action="store_true", help="the project owner approved a real API run of more than 30 records")
    ap.add_argument("--out-dir", type=Path, default=RESULTS_DIR)
    args = ap.parse_args(argv)
    try:
        decision = guards.check_split(args.split, final=args.final)
    except guards.Refused as e:
        sys.stderr.write(f"{e}\n")
        return 2
    if decision.warning:
        sys.stderr.write(decision.warning)
    kwargs = {"use_gazetteer": not args.no_gazetteer} if args.system in ("rules_only", "agent") else {}
    system = SYSTEMS[args.system](**kwargs)
    if not system.available:
        print(f"{system.name}: {system.unavailable_reason}")
        return 3
    budget = None
    if args.system == "agent":
        # The agent costs real money: dev only, a mandatory --limit, an estimate, a budget, and the session's 30-record rule.
        from agent.repair import worker
        from agent.repair.config import Prices, load_routing, run_budget_usd
        if args.split not in worker.ALLOWED_SPLITS:
            sys.stderr.write(f"REFUSED: the agent runs on {', '.join(worker.ALLOWED_SPLITS)} only today (calibration, hard and test are Day 5)\n")
            return 2
        if not args.limit or args.limit < 1:
            sys.stderr.write("REFUSED: --limit N is mandatory for the agent\n")
            return 2
        if args.limit > worker.UNAPPROVED_REAL_API_RECORDS and not args.approved_over_30:
            sys.stderr.write(f"REFUSED: more than {worker.UNAPPROVED_REAL_API_RECORDS} records against the real API needs the owner's approval (--approved-over-30)\n")
            return 2
        est = worker.estimate(args.limit, system.model, Prices.load(), load_routing())
        print(f"model {system.model}; estimate: {json.dumps(est)}")
        if args.limit > worker.CONFIRM_ABOVE and not args.yes:
            sys.stderr.write(f"REFUSED: more than {worker.CONFIRM_ABOVE} records need --yes after you have read the estimate\n")
            return 2
        budget = run_budget_usd()
    records = guards.load_records(decision)
    if args.limit:
        records = records[: args.limit]
    evals = run_system(system, records, budget)
    split_sha = hashlib.sha256(decision.path.read_bytes()).hexdigest()
    path = write_record(build_record(system, args.split, records, evals, split_sha=split_sha, limit=args.limit), args.out_dir)
    m = json.loads(path.read_text())["metrics"]
    fr = m["false_repair"]
    print(f"{system.name} on {args.split}: n={m['n']}  exact_all={m['exact_all']['k']}/{m['exact_all']['n']}  "
          f"false_repair={fr['k']}/{fr['n']}  wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
