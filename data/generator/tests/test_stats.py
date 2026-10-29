"""scripts/split_stats.py and addrgen.stats."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from addrgen.splits import dump_jsonl
from addrgen.stats import format_stats, read_jsonl, split_stats

REPO = Path(__file__).resolve().parents[3]

RECS = [
    {"country": "IE", "difficulty": "easy", "tags": []},
    {"country": "IE", "difficulty": "hard", "tags": ["typo", "county"]},
    {"country": "GB", "difficulty": "hard", "tags": ["typo"]},
]


def test_counts_by_country_difficulty_and_tag():
    s = split_stats(RECS)
    assert dict(s["country"]) == {"IE": 2, "GB": 1}
    assert dict(s["difficulty"]) == {"easy": 1, "hard": 2}
    assert dict(s["tag"]) == {"typo": 2, "county": 1}


def test_format_lists_every_section_with_percentages():
    text = format_stats(RECS)
    assert text.startswith("3 records")
    for heading in ("by country", "by difficulty", "by tag"):
        assert heading in text
    assert "typo" in text and "66.7%" in text


def test_empty_split_does_not_crash():
    assert format_stats([]).startswith("0 records")


def test_script_reads_a_named_split_and_a_path(tmp_path):
    path = tmp_path / "x.jsonl"
    path.write_bytes(dump_jsonl([dict(r, id=str(i)) for i, r in enumerate(RECS)]))
    assert len(read_jsonl(path)) == 3
    result = subprocess.run([sys.executable, str(REPO / "scripts" / "split_stats.py"), str(path), "dev"],
                            capture_output=True, text=True)
    assert result.returncode == 0
    assert "== dev ==" in result.stdout and "600 records" in result.stdout and "by tag" in result.stdout
