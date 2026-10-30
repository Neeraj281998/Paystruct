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


def run_system(system, records: list[dict]) -> list:
    evals = []
    for rec in records:
        out = system.run(rec["raw_lines"], rec.get("country_hint"))
        evals.append(evaluate_record(rec, out))
    return evals


def build_record(system, split: str, records: list[dict], evals: list, seed: int = 0, split_sha: str = "") -> dict:
    return {
        "git_sha": git("rev-parse", "HEAD"),
        "git_dirty": bool(git("status", "--porcelain", "--untracked-files=no")),
        "date": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "system": system.name,
        "split": split,
        "n_records": len(records),
        "split_sha256": split_sha,
        "seed": seed,
        "config": system.config(),
        "metrics": compute(evals),
    }


def write_record(record: dict, out_dir: Path = RESULTS_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = record["date"].replace(":", "").replace("-", "")
    path = out_dir / f"{stamp}_{record['system']}_{record['split']}_{record['git_sha'][:7]}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--system", required=True, choices=sorted(SYSTEMS))
    ap.add_argument("--split", required=True)
    ap.add_argument("--final", action="store_true", help="required for the test split (refused in this session)")
    ap.add_argument("--no-gazetteer", action="store_true", help="rules_only without the GeoNames file (what CI can run)")
    ap.add_argument("--out-dir", type=Path, default=RESULTS_DIR)
    args = ap.parse_args(argv)
    try:
        decision = guards.check_split(args.split, final=args.final)
    except guards.Refused as e:
        sys.stderr.write(f"{e}\n")
        return 2
    if decision.warning:
        sys.stderr.write(decision.warning)
    system = SYSTEMS[args.system](use_gazetteer=not args.no_gazetteer) if args.system == "rules_only" else SYSTEMS[args.system]()
    if not system.available:
        print(f"{system.name}: {system.unavailable_reason}")
        return 3
    records = guards.load_records(decision)
    evals = run_system(system, records)
    split_sha = hashlib.sha256(decision.path.read_bytes()).hexdigest()
    path = write_record(build_record(system, args.split, records, evals, split_sha=split_sha), args.out_dir)
    m = json.loads(path.read_text())["metrics"]
    fr = m["false_repair"]
    print(f"{system.name} on {args.split}: n={m['n']}  exact_all={m['exact_all']['k']}/{m['exact_all']['n']}  "
          f"false_repair={fr['k']}/{fr['n']}  wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
