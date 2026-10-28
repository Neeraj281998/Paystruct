"""Generates records: pick a structure and a set of corruptions for a target difficulty, render, and keep the attempt
only if the computed difficulty matches the target and the record is valid."""
from __future__ import annotations

import random

from addrgen import countries
from addrgen.difficulty import DIFFICULTIES, difficulty_of
from addrgen.render import CORRUPTIONS, RenderError, render
from addrgen.validate import check_record

DEFAULT_TYPO_RATE = 0.25  # of hard records (typo makes a record hard), so about a twelfth of a balanced set
MAX_ATTEMPTS = 500

# How many corruptions to apply, per tier: (count, weight).
_COUNTS = {
    "easy": ((0, 45), (1, 55)),
    "medium": ((0, 15), (1, 20), (2, 35), (3, 30)),
    "hard": ((1, 10), (2, 20), (3, 25), (4, 25), (5, 20)),
}
_EASY_POOL = (("country_name", 3), ("missing_commas", 3), ("all_caps", 2), ("extra_spaces", 2), ("abbreviated", 3),
              ("one_line", 1), ("reordered", 1))
_MEDIUM_POOL = (("country_name", 3), ("missing_commas", 3), ("all_caps", 2), ("extra_spaces", 2), ("abbreviated", 3),
                ("one_line", 2), ("reordered", 2))
# typo is not here: it is decided per record from the typo rate.
_HARD_POOL = (("country_name", 2), ("missing_commas", 2), ("all_caps", 2), ("extra_spaces", 2), ("abbreviated", 2),
              ("one_line", 2), ("reordered", 2), ("no_country", 3), ("postcode_split", 2), ("postcode_wrong_line", 2),
              ("postcode_no_space", 2))
_POOLS = {"easy": _EASY_POOL, "medium": _MEDIUM_POOL, "hard": _HARD_POOL}

# Corruptions that cannot be combined on one record.
_CONFLICTS = (
    {"postcode_split", "postcode_wrong_line", "postcode_no_space"},
    {"no_country", "country_name"},
    {"one_line", "postcode_split"},
    {"one_line", "postcode_wrong_line"},
    {"reordered", "postcode_split"},
    {"reordered", "postcode_wrong_line"},
)
assert all(name in CORRUPTIONS for pool in _POOLS.values() for name, _ in pool)


def _conflicts(chosen: set[str], name: str) -> bool:
    return any(name in group and chosen & (group - {name}) for group in _CONFLICTS)


def sample_ops(rng: random.Random, difficulty: str) -> set[str]:
    counts, weights = zip(*_COUNTS[difficulty])
    wanted = rng.choices(counts, weights=weights)[0]
    pool = list(_POOLS[difficulty])
    chosen: set[str] = set()
    while len(chosen) < wanted:
        options = [(n, w) for n, w in pool if n not in chosen and not _conflicts(chosen, n)]
        if not options:
            break
        chosen.add(rng.choices([n for n, _ in options], weights=[w for _, w in options])[0])
    return chosen


def record_rng(seed: int, country: str, index: int, difficulty: str) -> random.Random:
    return random.Random(f"{seed}|{country}|{index}|{difficulty}")


def generate_record(seed: int, country: str, index: int, difficulty: str, typo_rate: float = DEFAULT_TYPO_RATE) -> dict:
    """One record. The same (seed, country, index, difficulty, typo_rate) always gives the same record."""
    if difficulty not in DIFFICULTIES:
        raise ValueError(f"unknown difficulty {difficulty!r}")
    module = countries.get(country)
    rng = record_rng(seed, module.code, index, difficulty)
    wants_typo = difficulty == "hard" and rng.random() < typo_rate

    for _ in range(MAX_ATTEMPTS):
        truth = module.make_truth(rng, difficulty)
        ops = sample_ops(rng, difficulty) | ({"typo"} if wants_typo else set())
        try:
            rendered = render(truth, ops, module, rng)
        except RenderError:
            continue
        if difficulty_of(rendered.tags) != difficulty or wants_typo != ("typo" in rendered.tags):
            continue
        record = {
            "id": f"{module.code.lower()}-{index:05d}",
            "country": module.code,
            "difficulty": difficulty,
            "tags": sorted(rendered.tags),
            "raw_lines": rendered.raw_lines,
            "gold": rendered.gold,
        }
        if rendered.country_hint:
            record["country_hint"] = rendered.country_hint
        if not check_record(record):
            return record
    raise RuntimeError(f"no valid {difficulty} record for {country} #{index} after {MAX_ATTEMPTS} attempts")


def generate(seed: int, count: int, country_codes: list[str], difficulties: list[str] | None = None,
             start_index: int = 0, typo_rate: float = DEFAULT_TYPO_RATE):
    """Records round-robin over the countries; within a country the tier cycles, so tiers stay balanced."""
    tiers = difficulties or list(DIFFICULTIES)
    for n in range(count):
        country = country_codes[n % len(country_codes)]
        index = start_index + n // len(country_codes)
        yield generate_record(seed, country, index, tiers[index % len(tiers)], typo_rate)
