#!/usr/bin/env python3
"""Fails if any ground-truth address or id is in two splits. Does not parse the frozen test split (see split_check)."""
import argparse
from pathlib import Path

import _path  # noqa: F401
from addrgen.split_check import check_splits


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--splits-dir", type=Path, default=_path.REPO_ROOT / "data/splits")
    p.add_argument("--include-test-file", action="store_true",
                   help="also parse test.jsonl and compare it with the manifest (for the project owner)")
    args = p.parse_args()
    problems = check_splits(args.splits_dir, parse_test=args.include_test_file)
    for line in problems:
        print("FAIL:", line)
    if not problems:
        print("OK: splits are disjoint (no shared address, no shared id)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
