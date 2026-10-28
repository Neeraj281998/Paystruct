"""python -m addrgen --seed 20261012 --count 100 --out sample.jsonl"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from addrgen import countries
from addrgen.difficulty import DIFFICULTIES
from addrgen.generate import DEFAULT_TYPO_RATE, generate


def write_jsonl(path: Path, records) -> int:
    n = 0
    # Explicit encoding and newline so the bytes are the same on every platform.
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            n += 1
    return n


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="addrgen", description="Generate synthetic labelled addresses (JSONL).")
    p.add_argument("--seed", type=int, required=True, help="random seed; the project seed is recorded in data/generator/SEED")
    p.add_argument("--count", type=int, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--countries", default=",".join(countries.codes()), help="comma-separated ISO codes")
    p.add_argument("--difficulties", default=",".join(DIFFICULTIES), help="tiers to cycle through")
    p.add_argument("--start-index", type=int, default=0, help="first record number within each country")
    p.add_argument("--typo-rate", type=float, default=DEFAULT_TYPO_RATE, help="fraction of hard records with a typo")
    args = p.parse_args(argv)

    codes = [c.strip().upper() for c in args.countries.split(",") if c.strip()]
    tiers = [d.strip() for d in args.difficulties.split(",") if d.strip()]
    n = write_jsonl(args.out, generate(args.seed, args.count, codes, tiers, args.start_index, args.typo_rate))
    print(f"wrote {n} records to {args.out} (seed {args.seed})", file=sys.stderr)
    return 0
