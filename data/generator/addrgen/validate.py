"""Checks a record against the XSD limits and the labelling guide. Used by the generator (to reject bad attempts) and
by the tests."""
from __future__ import annotations

import re

from addrgen.difficulty import DIFFICULTIES
from addrgen.limits import GOLD_FIELDS, LIMITS, MAX_LINE_LENGTH, MAX_LINES

_ID = re.compile(r"^[a-z]{2}-\d{5}$")


def check_record(rec: dict) -> list[str]:
    problems: list[str] = []
    for key in ("id", "country", "difficulty", "tags", "raw_lines", "gold"):
        if key not in rec:
            problems.append(f"missing key {key}")
    if problems:
        return problems

    if not _ID.match(rec["id"]):
        problems.append(f"bad id {rec['id']!r}")
    if rec["difficulty"] not in DIFFICULTIES:
        problems.append(f"bad difficulty {rec['difficulty']!r}")
    if rec["tags"] != sorted(set(rec["tags"])):
        problems.append("tags are not sorted and unique")

    lines = rec["raw_lines"]
    if not 1 <= len(lines) <= MAX_LINES:
        problems.append(f"{len(lines)} raw lines (limit {MAX_LINES})")
    for line in lines:
        if not line.strip():
            problems.append("blank raw line")
        if len(line) > MAX_LINE_LENGTH:
            problems.append(f"raw line over {MAX_LINE_LENGTH} characters: {len(line)}")

    gold = rec["gold"]
    for name, value in gold.items():
        if name not in GOLD_FIELDS:
            problems.append(f"gold element {name} is not used in v1")
            continue
        limit = LIMITS[name]
        if not value or value != value.strip():
            problems.append(f"{name} is empty or has outer whitespace")
        if "  " in value:
            problems.append(f"{name} has a double space inside the value")
        if limit.max_length is not None and len(value) > limit.max_length:
            problems.append(f"{name} is {len(value)} characters (XSD maximum {limit.max_length})")
        if limit.pattern is not None and not re.fullmatch(limit.pattern, value):
            problems.append(f"{name} {value!r} does not match the XSD pattern {limit.pattern}")
    if "Ctry" not in gold:
        problems.append("gold has no Ctry")
    if list(gold) != [f for f in GOLD_FIELDS if f in gold]:
        problems.append("gold elements are not in XSD order")
    if "PstBx" in gold and "StrtNm" in gold:
        problems.append("a PO box address has no StrtNm (guide section 7)")
    return problems
