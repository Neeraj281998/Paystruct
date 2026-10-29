"""Proves the splits are disjoint: no ground-truth address (country plus normalised gold) and no id is in two splits.

The frozen test split is never parsed here. Its address keys come from the hashes recorded in splits.manifest.json when
the splits were built, and the test file is tied to that manifest by its SHA-256. Pass parse_test=True (the
--include-test-file flag) to read the file itself; that is for the project owner, not for tuning.
"""
from __future__ import annotations

import json
from pathlib import Path

from addrgen.splits import SPLIT_FILES, file_sha256, key_hash
from addrgen.validate import check_record


def _read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def check_splits(splits_dir, parse_test: bool = False) -> list[str]:
    """Every problem found; an empty list means the splits are disjoint and consistent with the manifest."""
    d = Path(splits_dir)
    problems: list[str] = []
    manifest_path = d / "splits.manifest.json"
    if not manifest_path.exists():
        return [f"{manifest_path} is missing"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))["splits"]

    keys: dict[str, list[str]] = {}  # split -> key hashes (with repeats)
    ids: dict[str, str] = {}
    for name, filename in SPLIT_FILES.items():
        path = d / filename
        entry = manifest.get(name)
        if name == "test":
            if entry is None:
                problems.append("test is not in the manifest")
                continue
            if not path.exists():
                problems.append("test.jsonl is missing")
            elif file_sha256(path) != entry["sha256"]:
                problems.append("test.jsonl does not match the manifest hash")
            if parse_test and path.exists():
                recs = _read(path)
                if sorted(key_hash(r) for r in recs) != entry["key_hashes"]:
                    problems.append("test.jsonl addresses do not match the manifest key hashes")
            keys[name] = list(entry["key_hashes"])
            continue
        if not path.exists():
            if entry is not None:
                problems.append(f"{filename} is missing")
            continue
        records = _read(path)
        if entry is not None and file_sha256(path) != entry["sha256"]:
            problems.append(f"{filename} does not match the manifest hash")
        keys[name] = [key_hash(r) for r in records]
        for r in records:
            if name != "hard":  # the hand-written set is checked by its own validator
                problems += [f"{r.get('id')}: {p}" for p in check_record(r)]
            if r["id"] in ids:
                problems.append(f"id {r['id']} is in both {ids[r['id']]} and {name}")
            ids[r["id"]] = name

    for name, hashes in keys.items():
        if len(hashes) != len(set(hashes)):
            problems.append(f"{name} repeats an address ({len(hashes) - len(set(hashes))} duplicates)")
    names = list(keys)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            shared = set(keys[a]) & set(keys[b])
            if shared:
                problems.append(f"{len(shared)} ground-truth addresses are in both {a} and {b}")
    return problems
