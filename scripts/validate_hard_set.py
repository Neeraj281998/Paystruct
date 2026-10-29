#!/usr/bin/env python3
"""Validates data/hard_set/*.yaml: required fields, lengths, tags, and that gold is text from the raw lines."""
import argparse
from collections import Counter
from pathlib import Path

import _path  # noqa: F401
from addrgen.hardset import TARGET_SIZE, validate_dir


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dir", type=Path, default=_path.REPO_ROOT / "data/hard_set")
    args = p.parse_args()
    problems, entries = validate_dir(args.dir)
    for line in problems:
        print("FAIL:", line)
    real = Counter(c for c, e in entries if not e.get("example"))
    examples = sum(1 for _, e in entries if e.get("example"))
    print(f"{sum(real.values())} of {TARGET_SIZE} hand-written entries, {examples} examples "
          f"(per country: {dict(sorted(real.items())) or 'none yet'})")
    if not problems:
        print("OK: every entry is valid")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
