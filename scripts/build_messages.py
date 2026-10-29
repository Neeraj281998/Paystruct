#!/usr/bin/env python3
"""Builds sample pacs.008 / pain.001 messages from a split into data/messages/, with manifest.json (gold + fault per job)."""
import argparse
from pathlib import Path

import _path  # noqa: F401
from addrgen.messages import build_messages, write_messages
from addrgen.stats import read_jsonl

REPO = _path.REPO_ROOT


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--seed", type=int, default=int((REPO / "data/generator/SEED").read_text()))
    p.add_argument("--count", type=int, default=300)
    p.add_argument("--split", default="dev", help="dev only by default; the frozen test split must not be used here")
    p.add_argument("--out", type=Path, default=REPO / "data/messages")
    args = p.parse_args()
    if args.split == "test":
        p.error("the frozen test split is never used to build sample messages")
    records = read_jsonl(REPO / "data/splits" / f"{args.split}.jsonl")
    manifest = write_messages(args.out, build_messages(records, args.seed, args.count), args.seed, args.split)
    print(f"wrote {manifest['messages']} messages ({manifest['jobs']} jobs) to {args.out}; faults {manifest['faults']}; "
          f"{manifest['xsd_valid']} validate against the XSD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
