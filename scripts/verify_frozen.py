#!/usr/bin/env python3
"""Fails if data/splits/test.jsonl no longer hashes to the value frozen in data/splits/test.sha256.

Only the file's bytes are hashed; nothing from the test split is printed. Standard library only.
"""
import hashlib
import sys
from pathlib import Path

SPLITS = Path(__file__).resolve().parents[1] / "data" / "splits"


def verify(splits_dir: Path | None = None) -> str | None:
    """None when the test split is intact, otherwise the reason it is not."""
    splits_dir = splits_dir or SPLITS
    sha_file, test_file = splits_dir / "test.sha256", splits_dir / "test.jsonl"
    if not sha_file.exists():
        return f"{sha_file} is missing, so the test split is not frozen"
    fields = sha_file.read_text().split()
    if not fields:
        return f"{sha_file} is empty"
    if not test_file.exists():
        return f"{test_file} is missing"
    h = hashlib.sha256()
    with open(test_file, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    if h.hexdigest() != fields[0]:
        return f"{test_file.name} has changed: expected {fields[0][:12]}..., got {h.hexdigest()[:12]}..."
    return None


def main() -> int:
    problem = verify()
    if problem:
        print("FAIL:", problem, file=sys.stderr)
        return 1
    print("OK: test split matches the frozen hash")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
