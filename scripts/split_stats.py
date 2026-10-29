#!/usr/bin/env python3
"""Prints counts by country, difficulty and tag for a split: dev, calibration, test, hard, or a path to a .jsonl file."""
import argparse
from pathlib import Path

import _path  # noqa: F401
from addrgen.stats import format_stats, read_jsonl

SPLITS = _path.REPO_ROOT / "data" / "splits"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("split", nargs="+", help="dev, calibration, test, hard, or a path")
    args = p.parse_args()
    for name in args.split:
        path = Path(name) if name.endswith(".jsonl") else SPLITS / f"{name}.jsonl"
        print(f"== {name} ==")
        print(format_stats(read_jsonl(path)))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
