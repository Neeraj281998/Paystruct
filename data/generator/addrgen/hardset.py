"""The hand-written hard set: one YAML file per country in data/hard_set/, a validator, and a converter to hard.jsonl.

The addresses are written by the project owner; nothing here invents them. Entries marked `example: true` show the
format and are left out of hard.jsonl unless asked for.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import yaml

from addrgen import countries
from addrgen.difficulty import CORRUPTION_TAGS, difficulty_of
from addrgen.limits import GOLD_FIELDS, LIMITS, MAX_LINE_LENGTH, MAX_LINES

TARGET_SIZE = 100
STRUCTURE_TAGS = frozenset({"no_street_number", "postal_district", "flat", "building_name", "floor", "po_box", "county",
                            "locality", "landmark", "cedex", "partial_postcode", "not_in_geonames", "no_town"})
KNOWN_TAGS = CORRUPTION_TAGS | STRUCTURE_TAGS
REQUIRED_GOLD = ("TwnNm", "Ctry")  # CBPR+ makes town and country mandatory; everything else is optional
# TwnNm may be missing only in a record tagged no_town (guide section 20), and must then be absent.
_ID = re.compile(r"^([a-z]{2})-(h\d{3}|x\d{2})$")  # h001 for a real entry, x01 for an example
_ENTRY_KEYS = {"id", "example", "tags", "raw_lines", "gold", "country_hint", "note"}


def _norm(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def load_file(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: expected a mapping with `country` and `entries`")
    return data


def validate_entry(entry: dict, country: str) -> list[str]:
    """Problems with one entry; an empty list means it is valid."""
    problems: list[str] = []
    unknown = set(entry) - _ENTRY_KEYS
    if unknown:
        problems.append(f"unknown keys {sorted(unknown)}")

    match = _ID.match(str(entry.get("id", "")))
    if not match:
        problems.append(f"id {entry.get('id')!r} must look like {country.lower()}-h001 (example: {country.lower()}-x01)")
    else:
        if match.group(1) != country.lower():
            problems.append(f"id prefix {match.group(1)!r} does not match the file country {country}")
        if bool(entry.get("example")) != match.group(2).startswith("x"):
            problems.append("ids starting x are examples, and only examples may use them (set `example: true`)")

    lines = entry.get("raw_lines")
    if not isinstance(lines, list) or not lines or not all(isinstance(x, str) for x in lines):
        problems.append("raw_lines must be a non-empty list of strings")
        lines = []
    if len(lines) > MAX_LINES:
        problems.append(f"{len(lines)} raw lines (limit {MAX_LINES})")
    for line in lines:
        if not line.strip():
            problems.append("blank raw line")
        if len(line) > MAX_LINE_LENGTH:
            problems.append(f"raw line over {MAX_LINE_LENGTH} characters ({len(line)}): {line[:30]!r}...")

    tags = entry.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        problems.append("tags must be a list of strings")
        tags = []
    if set(tags) - KNOWN_TAGS:
        problems.append(f"unknown tags {sorted(set(tags) - KNOWN_TAGS)}")
    if len(tags) != len(set(tags)):
        problems.append("duplicate tags")

    gold = entry.get("gold")
    if not isinstance(gold, dict) or not gold:
        problems.append("gold must be a mapping of element name to value")
        return problems
    no_town = "no_town" in tags
    for name in REQUIRED_GOLD:
        if name not in gold and not (no_town and name == "TwnNm"):
            problems.append(f"gold is missing the required {name}")
    if no_town and "TwnNm" in gold:
        problems.append("a no_town record has no TwnNm in gold (guide section 20)")
    text = _norm(" ".join(lines))
    for name, value in gold.items():
        if name not in GOLD_FIELDS:
            problems.append(f"gold element {name} is not used in v1")
            continue
        if not isinstance(value, str) or not value:
            problems.append(f"{name} must be a non-empty string")
            continue
        limit = LIMITS[name]
        if value != value.strip() or "  " in value:
            problems.append(f"{name} has outer whitespace or a double space")
        if limit.max_length is not None and len(value) > limit.max_length:
            problems.append(f"{name} is {len(value)} characters (XSD maximum {limit.max_length})")
        if limit.pattern is not None and not re.fullmatch(limit.pattern, value):
            problems.append(f"{name} {value!r} does not match the XSD pattern {limit.pattern}")
        if name != "Ctry" and _norm(value) not in text:  # guide section 0: gold is text from the raw lines
            problems.append(f"{name} {value!r} does not appear in the raw lines")
    if gold.get("Ctry") != country:
        problems.append(f"gold Ctry is {gold.get('Ctry')!r}, but the file is for {country}")
    if "PstBx" in gold and "StrtNm" in gold:
        problems.append("a PO box address has no StrtNm (guide section 7)")

    hint = entry.get("country_hint")
    if "no_country" in tags and hint != country:
        problems.append(f"no_country needs country_hint: {country}")
    if hint is not None and "no_country" not in tags:
        problems.append("country_hint is only for no_country entries")
    if "no_country" in tags and "country_name" in tags:
        problems.append("no_country and country_name cannot both be set")
    if entry.get("example") and not str(entry.get("note", "")).upper().startswith("EXAMPLE"):
        problems.append("an example entry's note must start with EXAMPLE")
    return problems


def validate_dir(directory: Path) -> tuple[list[str], list[tuple[str, dict]]]:
    """(problems, entries) over every country file. Entries are (file country, entry) in file order."""
    problems: list[str] = []
    entries: list[tuple[str, dict]] = []
    seen: set[str] = set()
    files = {p.stem.upper(): p for p in sorted(directory.glob("*.yaml"))}
    for code in countries.codes():
        if code not in files:
            problems.append(f"{code}.yaml is missing")
    for stem, path in files.items():
        if stem not in countries.codes():
            problems.append(f"{path.name}: {stem} is not a known country")
            continue
        try:
            data = load_file(path)
        except (ValueError, yaml.YAMLError) as e:
            problems.append(f"{path.name}: {e}")
            continue
        if data.get("country") != stem:
            problems.append(f"{path.name}: `country` must be {stem}, got {data.get('country')!r}")
        for i, entry in enumerate(data.get("entries") or [], start=1):
            label = f"{path.name} entry {i} ({entry.get('id') if isinstance(entry, dict) else '?'})"
            if not isinstance(entry, dict):
                problems.append(f"{label}: must be a mapping")
                continue
            problems += [f"{label}: {p}" for p in validate_entry(entry, stem)]
            if entry.get("id") in seen:
                problems.append(f"{label}: duplicate id")
            seen.add(entry.get("id"))
            entries.append((stem, entry))
    return problems, entries


def to_record(entry: dict) -> dict:
    """The JSONL record: the generator's format, with gold in XSD order and the tier computed from the tags."""
    tags = sorted(entry.get("tags", []))
    gold = {name: entry["gold"][name] for name in GOLD_FIELDS if name in entry["gold"]}
    record = {"id": entry["id"], "country": gold["Ctry"], "difficulty": difficulty_of(set(tags)), "tags": tags,
              "raw_lines": list(entry["raw_lines"]), "gold": gold}
    if entry.get("country_hint"):
        record["country_hint"] = entry["country_hint"]
    return record


def build_records(directory: Path, include_examples: bool = False, allow_partial: bool = False) -> list[dict]:
    """Validated records for hard.jsonl. Raises ValueError listing every problem, or if there are not TARGET_SIZE."""
    problems, entries = validate_dir(directory)
    if problems:
        raise ValueError("\n".join(problems))
    chosen = [e for _, e in entries if include_examples or not e.get("example")]
    if len(chosen) != TARGET_SIZE and not allow_partial:
        raise ValueError(f"{len(chosen)} entries, but the hard set has {TARGET_SIZE} (use --allow-partial while writing)")
    return [to_record(e) for e in sorted(chosen, key=lambda e: e["id"])]


def write_jsonl(path: Path, records: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
