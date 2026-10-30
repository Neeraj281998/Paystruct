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
from evals.metrics import compute, evaluate_record, record_details
from evals.systems import SYSTEMS, NotAvailable

RESULTS_DIR = guards.REPO_ROOT / "evals" / "results"
# Per-record details (input, output, gold, reasons, steps) are kept for tuning splits only. For the hard set and the test split a record
# keeps counts only, so nobody reads individual failures there.
PER_RECORD_SPLITS = ("dev", "calibration", "robustness")
ROBUSTNESS = "robustness"   # the 30 audit cases: a development-only source, not a split and not a result


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


def subset_label(limit: int | None, ids: list[str] | None) -> str | None:
    if ids:
        return "ids-" + hashlib.sha256(",".join(ids).encode()).hexdigest()[:8]
    return f"first{limit}" if limit else None


def robustness_records() -> list[dict]:
    """The 30 audit addresses of agent/audit/robustness_cases.py, scored against their 'want'. Development only."""
    from agent.audit.robustness_cases import CASES
    return [{"id": cid, "country": want["Ctry"], "raw_lines": lines, "gold": dict(want), "tags": [], "difficulty": "dev-only", "note": note}
            for cid, lines, want, note in CASES]


def build_record(system, split: str, records: list[dict], evals: list, seed: int = 0, split_sha: str = "", limit: int | None = None,
                 ids: list[str] | None = None) -> dict:
    rec = {
        "git_sha": git("rev-parse", "HEAD"),
        "git_dirty": bool(git("status", "--porcelain", "--untracked-files=no")),
        "date": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "system": system.name,
        "split": split,
        "n_records": len(evals),
        "limit": limit,
        "ids": ids,
        "subset": subset_label(limit, ids),
        "aborted_by_budget": len(evals) < len(records),
        "split_sha256": split_sha,
        "development_only": split == ROBUSTNESS,   # never a result: the report leaves these out of every table
        "seed": seed,
        "config": system.config(),
        "metrics": compute(evals),
    }
    if split in PER_RECORD_SPLITS:
        rec["records"] = [record_details(e) for e in evals]
    return rec


def write_record(record: dict, out_dir: Path = RESULTS_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = record["date"].replace(":", "").replace("-", "")
    tag = f"_{record['subset']}" if record.get("subset") else ""
    path = out_dir / f"{stamp}_{record['system']}_{record['split']}{tag}_{record['git_sha'][:7]}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--system", required=True, choices=sorted(SYSTEMS))
    ap.add_argument("--split")
    ap.add_argument("--source", choices=[ROBUSTNESS], help="a development-only source instead of a split: the 30 audit cases, not a result")
    ap.add_argument("--final", action="store_true", help="required for the test split (refused in this session)")
    ap.add_argument("--no-gazetteer", action="store_true", help="rules_only without the GeoNames file (what CI can run)")
    ap.add_argument("--limit", type=int, help="run only the first N records of the split (the agent needs --limit or --ids)")
    ap.add_argument("--ids", help="run only these record ids (comma-separated), e.g. to re-run a few failures; the agent needs --limit or --ids")
    ap.add_argument("--yes", action="store_true", help="required for the agent on more than 50 records, after reading the estimate")
    ap.add_argument("--approved-over-30", action="store_true", help="the project owner approved a real API run of more than 30 records")
    ap.add_argument("--out-dir", type=Path, default=RESULTS_DIR)
    args = ap.parse_args(argv)
    if args.source and args.split:
        sys.stderr.write("use --split or --source, not both\n")
        return 2
    if not args.source and not args.split:
        sys.stderr.write("--split (or --source robustness) is required\n")
        return 2
    decision = None
    if args.source:
        args.split = args.source
    else:
        try:
            decision = guards.check_split(args.split, final=args.final)
        except guards.Refused as e:
            sys.stderr.write(f"{e}\n")
            return 2
        if decision.warning:
            sys.stderr.write(decision.warning)
    ids = [i.strip() for i in args.ids.split(",") if i.strip()] if args.ids else None
    kwargs = {"use_gazetteer": not args.no_gazetteer} if args.system in ("rules_only", "agent") else {}
    system = SYSTEMS[args.system](**kwargs)
    if not system.available:
        print(f"{system.name}: {system.unavailable_reason}")
        return 3
    budget = None
    if args.system == "agent":
        # The agent costs real money: dev only, a mandatory --limit, an estimate, a budget, and the session's 30-record rule.
        from agent.repair import worker
        from agent.repair.config import load_routing, run_budget_usd
        if args.split not in worker.ALLOWED_SPLITS and args.split != ROBUSTNESS:
            sys.stderr.write(f"REFUSED: the agent runs on {', '.join(worker.ALLOWED_SPLITS)} only today (calibration, hard and test are Day 5); --source robustness is the development-only audit set\n")
            return 2
        if args.ids and args.limit:
            sys.stderr.write("REFUSED: use --limit or --ids, not both\n")
            return 2
        n_run = len(ids) if ids else args.limit
        if not n_run or n_run < 1:
            sys.stderr.write("REFUSED: --limit N or --ids is mandatory for the agent\n")
            return 2
        if n_run > worker.UNAPPROVED_REAL_API_RECORDS and not args.approved_over_30:
            sys.stderr.write(f"REFUSED: more than {worker.UNAPPROVED_REAL_API_RECORDS} records against the real API needs the owner's approval (--approved-over-30)\n")
            return 2
        budget = run_budget_usd()
    records = robustness_records() if args.source else guards.load_records(decision)
    if ids:
        by_id = {r["id"]: r for r in records}
        missing = [i for i in ids if i not in by_id]
        if missing:
            sys.stderr.write(f"unknown record ids for split {args.split}: {missing}\n")
            return 2
        records = [by_id[i] for i in ids]
    elif args.limit:
        records = records[: args.limit]
    if args.system == "agent":
        # run the rules offline (free), count what would reach the model, and price that from measured usage
        from agent.repair.config import load_routing
        from agent.repair.estimate import estimate_agent
        from agent.rules.engine import RulesEngine
        items = [(r["id"], r["raw_lines"], r.get("country_hint")) for r in records]
        print(f"model {system.model}; estimate: {json.dumps(estimate_agent(items, RulesEngine(), load_routing()))}")
        if len(records) > worker.CONFIRM_ABOVE and not args.yes:
            sys.stderr.write(f"REFUSED: more than {worker.CONFIRM_ABOVE} records need --yes after you have read the estimate\n")
            return 2
    evals = run_system(system, records, budget)
    source_file = guards.REPO_ROOT / "agent" / "audit" / "robustness_cases.py" if args.source else decision.path
    split_sha = hashlib.sha256(source_file.read_bytes()).hexdigest()
    path = write_record(build_record(system, args.split, records, evals, split_sha=split_sha, limit=args.limit, ids=ids), args.out_dir)
    m = json.loads(path.read_text())["metrics"]
    fr = m["false_repair"]
    label = f"{args.split} (development only, not a result)" if args.source else args.split
    print(f"{system.name} on {label}: n={m['n']}  exact_all={m['exact_all']['k']}/{m['exact_all']['n']}  "
          f"false_repair={fr['k']}/{fr['n']}  wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
