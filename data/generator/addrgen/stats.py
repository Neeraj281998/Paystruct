"""Counts by country, difficulty and tag for a split file."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def read_jsonl(path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def split_stats(records: list[dict]) -> dict[str, Counter]:
    return {
        "country": Counter(r["country"] for r in records),
        "difficulty": Counter(r["difficulty"] for r in records),
        "tag": Counter(t for r in records for t in r["tags"]),
    }


def format_stats(records: list[dict]) -> str:
    total = len(records)
    lines = [f"{total} records"]
    for title, counter in split_stats(records).items():
        lines.append(f"\nby {title}")
        width = max((len(k) for k in counter), default=0)
        for key, n in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]) if title == "tag" else (kv[0], 0)):
            lines.append(f"  {key:<{width}}  {n:>5}  {100 * n / total:5.1f}%")
    return "\n".join(lines)
