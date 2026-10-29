#!/usr/bin/env python3
"""Builds data/splits/{dev,calibration,test}.jsonl, splits.manifest.json and test.sha256 from the project seed.

Once test.sha256 exists the test split is frozen and is never rewritten.
"""
import argparse
from pathlib import Path

import _path  # noqa: F401
from addrgen.splits import write_splits

REPO = _path.REPO_ROOT


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--seed", type=int, default=int((REPO / "data/generator/SEED").read_text()))
    p.add_argument("--out", type=Path, default=REPO / "data/splits")
    args = p.parse_args()
    manifest = write_splits(args.out, args.seed)
    for name, m in manifest["splits"].items():
        print(f"{name}: {m['records']} records, sha256 {m['sha256'][:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
