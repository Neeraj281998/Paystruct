from __future__ import annotations

import pytest

from addrgen.difficulty import CORRUPTION_TAGS, difficulty_of


@pytest.mark.parametrize("tags, expected", [
    (set(), "easy"),
    ({"abbreviated"}, "easy"),
    ({"county", "locality", "po_box"}, "easy"),            # structure tags that do not raise the tier
    ({"abbreviated", "all_caps"}, "medium"),
    ({"abbreviated", "all_caps", "one_line"}, "medium"),
    ({"flat"}, "medium"),
    ({"building_name"}, "medium"),
    ({"floor"}, "medium"),
    ({"no_street_number"}, "medium"),
    ({"abbreviated", "all_caps", "one_line", "extra_spaces"}, "hard"),   # four corruptions
    ({"postal_district"}, "hard"),
    ({"no_country"}, "hard"),
    ({"postcode_split"}, "hard"),
    ({"postcode_wrong_line"}, "hard"),
    ({"typo"}, "hard"),
    ({"flat", "typo"}, "hard"),
])
def test_difficulty_follows_the_guide(tags, expected):
    assert difficulty_of(tags) == expected


def test_postcode_no_space_alone_is_not_hard():
    assert difficulty_of({"postcode_no_space"}) == "easy"


def test_corruption_tag_list_matches_the_guide():
    assert CORRUPTION_TAGS == {"all_caps", "extra_spaces", "one_line", "missing_commas", "reordered", "postcode_split",
                               "postcode_no_space", "postcode_wrong_line", "typo", "abbreviated", "country_name",
                               "no_country", "long_line_split"}
