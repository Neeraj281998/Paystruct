"""Difficulty tier, computed from tags exactly as data/labelling-guide.md section 11 defines it."""
from __future__ import annotations

CORRUPTION_TAGS = frozenset({
    "all_caps", "extra_spaces", "one_line", "missing_commas", "reordered", "postcode_split", "postcode_no_space",
    "postcode_wrong_line", "typo", "abbreviated", "country_name", "no_country", "long_line_split",
})
HARD_TAGS = frozenset({"postal_district", "no_country", "postcode_split", "postcode_wrong_line", "typo", "landmark", "cedex"})
MEDIUM_TAGS = frozenset({"no_street_number", "flat", "building_name", "floor"})
DIFFICULTIES = ("easy", "medium", "hard")


def difficulty_of(tags: set[str] | frozenset[str]) -> str:
    corruptions = len(tags & CORRUPTION_TAGS)
    if corruptions >= 4 or tags & HARD_TAGS:
        return "hard"
    if 2 <= corruptions <= 3 or tags & MEDIUM_TAGS:
        return "medium"
    return "easy"
