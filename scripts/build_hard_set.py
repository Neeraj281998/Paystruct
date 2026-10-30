#!/usr/bin/env python3
"""Converts data/hard_set/*.yaml into data/splits/hard.jsonl (examples are left out unless asked for)."""
import argparse
from pathlib import Path

import _path  # noqa: F401
from addrgen.hardset import DEFAULT_MINIMUM, build_records, write_jsonl

REPO = _path.REPO_ROOT


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dir", type=Path, default=REPO / "data/hard_set")
    p.add_argument("--out", type=Path, default=REPO / "data/splits/hard.jsonl")
    p.add_argument("--include-examples", action="store_true", help="also write the entries marked example")
    p.add_argument("--min-entries", type=int, default=DEFAULT_MINIMUM, help="fewest real entries to accept (default %(default)s)")
    args = p.parse_args()
    try:
        records = build_records(args.dir, args.include_examples, args.min_entries)
    except ValueError as e:
        print(f"FAIL:\n{e}")
        return 1
    write_jsonl(args.out, records)
    print(f"wrote {len(records)} records to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
