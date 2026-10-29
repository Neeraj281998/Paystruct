from __future__ import annotations

import random

import pytest

from addrgen import corrupt, countries
from addrgen.model import Part, Truth
from addrgen.render import RenderError, render
from tests.helpers import written_text

IE = countries.get("IE")


def P(field, text):
    return Part(field, text)


# ---- text-level -------------------------------------------------------------------------------------------------
def test_abbreviate_street_and_apartment_words():
    for seed in range(20):
        parts = [P("StrtNm", "Main Street"), P("Room", "Apartment 5"), P("TwnNm", "Street")]
        assert corrupt.abbreviate(parts, random.Random(seed), IE)
        assert parts[0].text in ("Main St", "Main St.")
        assert parts[1].text in ("Apt 5", "Apt. 5")
        assert parts[2].text == "Street"  # only street and room fields are abbreviated


def test_abbreviate_does_nothing_without_an_abbreviable_word():
    parts = [P("StrtNm", "Main Way"), P("Room", "Flat 2")]
    assert not corrupt.abbreviate(parts, random.Random(1), IE)
    assert [p.text for p in parts] == ["Main Way", "Flat 2"]


def test_typo_touches_one_word_of_one_street_or_building_name_only():
    for seed in range(300):
        parts = [P("StrtNm", "Kavanagh Road"), P("BldgNm", "Riverside Court"), P("TwnNm", "Galway"),
                 P("PstCd", "H91 AB12"), P("BldgNb", "12"), P("Ctry", "Ireland")]
        before = [p.text for p in parts]
        assert corrupt.typo(parts, random.Random(seed), IE)
        changed = [i for i, (a, p) in enumerate(zip(before, parts)) if a != p.text]
        assert len(changed) == 1 and parts[changed[0]].field in ("StrtNm", "BldgNm")
        old, new = before[changed[0]].split(" "), parts[changed[0]].text.split(" ")
        assert len(old) == len(new)
        diff = [i for i, (a, b) in enumerate(zip(old, new)) if a != b]
        assert len(diff) == 1
        assert new[diff[0]][0] == old[diff[0]][0]            # never the first letter
        assert old[diff[0]] not in ("Road", "Court")           # never the street or building word
        assert abs(len(new[diff[0]]) - len(old[diff[0]])) <= 1


def test_typo_never_applies_to_a_town_postcode_number_or_country():
    parts = [P("TwnNm", "Letterkenny"), P("PstCd", "F92 1VXA"), P("BldgNb", "12"), P("Ctry", "Ireland"),
             P("TwnLctnNm", "Ballincollig")]
    assert not corrupt.typo(parts, random.Random(1), IE)


def test_typo_needs_a_word_long_enough_to_break():
    assert not corrupt.typo([P("StrtNm", "Main Street")], random.Random(1), IE)  # "Main" has 4 letters


def test_postcode_no_space_and_all_caps():
    parts = [P("PstCd", "D01 K2X7"), P("TwnNm", "Dún Laoghaire")]
    assert corrupt.postcode_no_space(parts) and parts[0].text == "D01K2X7"
    assert corrupt.all_caps(parts) and parts[1].text == "DÚN LAOGHAIRE"
    assert not corrupt.all_caps([P("PstCd", "D01K2X7")])  # already capitals: no change, so no tag


# ---- layout-level -----------------------------------------------------------------------------------------------
def _segments():
    return [[P("BldgNb", "12"), P("StrtNm", "Main Street")], [P("TwnLctnNm", "Salthill")],
            [P("TwnNm", "Galway"), P("PstCd", "H91 AB12")], [P("Ctry", "IE")]]


def _flat(segments):
    return sorted((p.field, p.text) for seg in segments for p in seg)


@pytest.mark.parametrize("seed", range(30))
def test_reorder_changes_the_order_but_never_a_value(seed):
    segments = _segments()
    before = _flat(segments)
    assert corrupt.reorder(segments, random.Random(seed))
    assert _flat(segments) == before
    assert [[(p.field, p.text) for p in s] for s in segments] != [[(p.field, p.text) for p in s] for s in _segments()]


@pytest.mark.parametrize("seed", range(30))
def test_postcode_wrong_line_moves_only_the_postcode(seed):
    segments = _segments()
    assert corrupt.postcode_wrong_line(segments, random.Random(seed))
    assert _flat(segments) == _flat(_segments())
    line_of_town = next(s for s in segments if any(p.field == "TwnNm" for p in s))
    assert all(p.field != "PstCd" for p in line_of_town)


def test_postcode_split_ends_one_line_and_starts_the_next():
    segments = _segments()
    assert corrupt.postcode_split(segments, random.Random(1), ("H91", "AB12"))
    assert [p.text for p in segments[2]] == ["Galway", "H91"]
    assert [p.text for p in segments[3]] == ["AB12", "IE"]


def test_postcode_split_makes_a_new_line_when_nothing_follows():
    segments = [[P("TwnNm", "Galway"), P("PstCd", "H91 AB12")]]
    assert corrupt.postcode_split(segments, random.Random(1), ("H91", "AB12"))
    assert [[p.text for p in s] for s in segments] == [["Galway", "H91"], ["AB12"]]


def test_layout_corruptions_report_no_change_when_there_is_nothing_to_do():
    assert not corrupt.postcode_wrong_line([[P("StrtNm", "Main Street")]], random.Random(1))
    assert not corrupt.postcode_split([[P("StrtNm", "Main Street")]], random.Random(1), ("a", "b"))
    assert not corrupt.reorder([[P("StrtNm", "Main Street")]], random.Random(1))


# ---- through the renderer ---------------------------------------------------------------------------------------
def _truth(segments=None):
    return Truth("IE", "test", segments or [
        [P("Room", "Unit 4"), P("BldgNm", "Block B Docklands Business Park")],
        [P("TwnNm", "Dublin 1"), P("PstCd", "D01 K2X7")]], {"postal_district"})


def _render(ops, seed=1, truth=None):
    r = render(truth or _truth(), set(ops), IE, random.Random(seed))
    return r, {"raw_lines": r.raw_lines}


def test_the_spec_example_renders_and_keeps_its_gold():
    r, rec = _render([])
    assert r.gold == {"BldgNm": "Block B Docklands Business Park", "Room": "Unit 4", "PstCd": "D01 K2X7",
                      "TwnNm": "Dublin 1", "Ctry": "IE"}
    assert r.tags == {"postal_district"}
    assert "Block B Docklands Business Park" in written_text(rec)


def test_missing_commas_leaves_no_comma():
    r, _ = _render(["missing_commas"])
    assert "missing_commas" in r.tags and not any("," in l for l in r.raw_lines)


def test_missing_commas_is_not_tagged_when_there_was_no_comma_to_leave_out():
    # One value on one line, no country: there is nowhere a comma could go.
    r, _ = _render(["missing_commas", "no_country"], truth=_truth([[P("TwnNm", "Galway")]]))
    assert "missing_commas" not in r.tags


def test_one_line():
    r, _ = _render(["one_line"])
    assert "one_line" in r.tags and len(r.raw_lines) == 1


def test_country_as_a_name_or_absent():
    r, _ = _render(["country_name"])
    assert "country_name" in r.tags and r.gold["Ctry"] == "IE"
    assert any(name in " ".join(r.raw_lines) for name in IE.country_names)
    r, _ = _render(["no_country"])
    assert "no_country" in r.tags and r.country_hint == "IE" and r.gold["Ctry"] == "IE"
    assert "IE" not in " ".join(r.raw_lines).split() and "Ireland" not in " ".join(r.raw_lines)


def test_all_caps_changes_gold_to_the_text_as_written():
    r, _ = _render(["all_caps"])
    assert r.gold["TwnNm"] == "DUBLIN 1" and r.gold["BldgNm"] == "BLOCK B DOCKLANDS BUSINESS PARK"
    assert r.gold["Ctry"] == "IE"
    assert all(l == l.upper() for l in r.raw_lines)


def test_extra_spaces_never_go_inside_a_value():
    for seed in range(40):
        r, rec = _render(["extra_spaces"], seed=seed)
        assert "extra_spaces" in r.tags
        assert all("  " not in v for v in r.gold.values())
        for name, value in r.gold.items():
            if name != "Ctry":
                assert value in written_text(rec)


def test_postcode_no_space_changes_the_gold():
    r, _ = _render(["postcode_no_space"])
    assert r.gold["PstCd"] == "D01K2X7" and "postcode_no_space" in r.tags


def test_postcode_split_keeps_the_whole_postcode_in_gold():
    r, _ = _render(["postcode_split"])
    assert r.gold["PstCd"] == "D01 K2X7" and "postcode_split" in r.tags
    assert any(l.rstrip(",").rstrip().endswith("D01") for l in r.raw_lines)
    assert any(l.strip().startswith("K2X7") for l in r.raw_lines)


def test_lines_over_70_characters_are_split_and_gold_stays_whole():
    long_name = "Block C Docklands Business Park and Enterprise Centre Extension Wing"
    truth = _truth([[P("BldgNm", long_name)], [P("TwnNm", "Galway"), P("PstCd", "H91 AB12")]])
    r, rec = _render(["one_line"], truth=truth)
    assert "long_line_split" in r.tags and len(r.raw_lines) > 1
    assert all(len(l) <= 70 for l in r.raw_lines)
    assert r.gold["BldgNm"] == long_name and long_name in written_text(rec)


def test_a_line_that_cannot_be_wrapped_is_rejected_not_emitted():
    truth = _truth([[P("BldgNm", "X" * 90)], [P("TwnNm", "Galway"), P("PstCd", "H91 AB12")]])
    with pytest.raises(RenderError):
        _render([], truth=truth)


def test_too_many_lines_is_rejected():
    segments = [[P("BldgNm", f"Building {i}")] for i in range(8)]
    with pytest.raises(RenderError):
        render(Truth("IE", "t", segments, set()), set(), IE, random.Random(1))


def test_the_same_inputs_render_identically():
    assert _render(["all_caps", "extra_spaces", "reordered"], seed=5)[0] == _render(["all_caps", "extra_spaces", "reordered"], seed=5)[0]


def test_postcode_split_when_the_postcode_starts_its_line():
    """Postcode before town (NL, DE, FR): the first half ends the previous line and the second half stays."""
    segments = [[P("StrtNm", "Keizersgracht"), P("BldgNb", "99")], [P("PstCd", "1015 CJ"), P("TwnNm", "Amsterdam")]]
    assert corrupt.postcode_split(segments, random.Random(1), ("1015", "CJ"))
    assert [[p.text for p in s] for s in segments] == [["Keizersgracht", "99", "1015"], ["CJ", "Amsterdam"]]


def test_postcode_split_leaves_a_postcode_in_the_middle_of_a_line_alone():
    segments = [[P("TwnNm", "Austin"), P("PstCd", "78701"), P("CtrySubDvsn", "TX")]]
    assert not corrupt.postcode_split(segments, random.Random(1), ("787", "01"))


def test_a_comma_after_a_part_is_written_inside_the_line_and_dropped_when_commas_are_missing():
    truth = Truth("IE", "t", [[P("BldgNb", "12"), P("StrtNm", "Main Street")],
                              [Part("TwnNm", "Galway", comma_after=True), P("CtrySubDvsn", "Co. Galway")]], set())
    with_commas = render(truth, set(), IE, random.Random(1))
    assert any("Galway, Co. Galway" in l for l in with_commas.raw_lines)
    without = render(truth, {"missing_commas"}, IE, random.Random(1))
    assert not any("," in l for l in without.raw_lines) and "missing_commas" in without.tags


def test_unlabelled_text_is_written_but_never_in_gold():
    truth = Truth("IE", "t", [[P("StrtNm", "Main Street")], [Part(None, "near City Mall")], [P("TwnNm", "Galway")]], set())
    r = render(truth, {"all_caps"}, IE, random.Random(1))
    assert any("NEAR CITY MALL" in l for l in r.raw_lines)
    assert "NEAR CITY MALL" not in " ".join(r.gold.values()) and set(r.gold) == {"StrtNm", "TwnNm", "Ctry"}


def test_extra_spaces_is_only_tagged_if_a_space_survives_the_line_wrapping():
    """A trailing space at a wrap point is stripped; the tag must follow the final lines, not the request."""
    for seed in range(200):
        truth = Truth("IE", "t", [[P("BldgNm", "Block C Docklands Business Park and Enterprise Centre"), P("StrtNm", "Main Street")]], set())
        r = render(truth, {"extra_spaces", "one_line"}, IE, random.Random(seed))
        has_extra = any(l != l.strip() or "  " in l for l in r.raw_lines)
        assert ("extra_spaces" in r.tags) == has_extra, (seed, r.raw_lines)
