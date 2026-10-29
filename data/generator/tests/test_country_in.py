"""India (guide section 18)."""
from __future__ import annotations

import re
from collections import Counter

from addrgen.countries import in_
from tests.helpers import is_contiguous_span, tokens, written_text

CITIES = {c[0].casefold(): c for c in in_.CITIES}
LANDMARK_TOKENS = {" ".join(text.split()).casefold() for text in in_._LANDMARKS}


def test_pin_is_six_digits_and_belongs_to_the_city(by_country):
    for rec in by_country["IN"]:
        digits = rec["gold"]["PstCd"].replace(" ", "")
        assert re.fullmatch(r"\d{6}", digits) and digits[0] != "0", rec["id"]
        assert digits[:3] == CITIES[rec["gold"]["TwnNm"].casefold()][2], rec["id"]


def test_the_pin_is_also_written_with_a_space_and_never_dropped_as_a_corruption(by_country):
    pins = [r["gold"]["PstCd"] for r in by_country["IN"]]
    assert any(" " in p for p in pins) and any(" " not in p for p in pins)
    assert not any("postcode_no_space" in r["tags"] for r in by_country["IN"])


def test_state_is_always_written_and_matches_the_city(by_country):
    for rec in by_country["IN"]:
        assert rec["gold"]["CtrySubDvsn"].casefold() == CITIES[rec["gold"]["TwnNm"].casefold()][1].casefold(), rec["id"]


def test_a_locality_is_only_ever_beside_its_own_city(by_country):
    """Localities are tied to their city; a sector number only belongs to a planned city."""
    checked = sectors = 0
    for rec in by_country["IN"]:
        gold = rec["gold"]
        if "TwnLctnNm" not in gold:
            continue
        checked += 1
        town, locality = gold["TwnNm"].casefold(), gold["TwnLctnNm"].casefold()
        if re.fullmatch(r"sector \d+", locality):
            sectors += 1
            assert town in in_.SECTOR_TOWNS, (rec["id"], gold["TwnLctnNm"], gold["TwnNm"])
        else:
            assert locality in in_.LOCALITIES_BY_TOWN[town], (rec["id"], gold["TwnLctnNm"], gold["TwnNm"])
    assert checked > 300 and sectors > 20


def test_a_sector_never_appears_beside_a_city_that_has_none(by_country):
    for rec in by_country["IN"]:
        if re.fullmatch(r"(?i)sector \d+", rec["gold"].get("TwnLctnNm", "")):
            assert rec["gold"]["TwnNm"].casefold() in {"noida", "gurugram", "chandigarh"}


def test_plot_house_and_door_numbers_keep_their_keyword_and_fit(by_country):
    forms = set()
    for rec in by_country["IN"]:
        nb = rec["gold"].get("BldgNb")
        if nb:
            assert len(nb) <= 16 and re.fullmatch(r"(?i)(Plot \d+|House No\. \d+|Door No\. \d+-\d-\d+|No\. \d+)", nb), nb
            forms.add(nb.split(" ")[0].upper().rstrip("."))
    assert {"PLOT", "HOUSE", "DOOR", "NO"} <= forms


def test_flats_floors_and_no_po_box(by_country):
    for rec in by_country["IN"]:
        gold = rec["gold"]
        assert "PstBx" not in gold
        if "Room" in gold:
            assert re.fullmatch(r"(?i)Flat( No\.)? \d+", gold["Room"])
        if "Flr" in gold:
            assert re.fullmatch(r"(?i)\d+(st|nd|rd|th) floor", gold["Flr"])


def test_roads_and_buildings_use_the_listed_words(by_country):
    streets, buildings = set(), set()
    for rec in by_country["IN"]:
        if "StrtNm" in rec["gold"]:
            streets.add(rec["gold"]["StrtNm"].split(" ")[-1].casefold().rstrip("."))
        if "BldgNm" in rec["gold"]:
            buildings.add(rec["gold"]["BldgNm"].split(" ")[-1].casefold())
    assert {"road", "marg", "street", "lane", "cross"} <= streets | {"rd"}
    assert {"residency", "towers", "heights", "apartments", "plaza", "complex", "mansion"} <= buildings


def test_landmarks_are_unlabelled_one_contiguous_span_and_hard(by_country):
    landmark = [r for r in by_country["IN"] if "landmark" in r["tags"]]
    assert len(landmark) > 50
    for rec in landmark:
        assert rec["difficulty"] == "hard"
        raw_tokens = written_text(rec).split()
        gold = Counter(t for n, v in rec["gold"].items() if n != "Ctry" for t in v.split())
        rest = tokens(written_text(rec)) - gold
        country = [Counter(w.split()) for w in ("IN", "India", "INDIA")]
        left = next(rest - c for c in country if not (c - rest)) if "no_country" not in rec["tags"] else rest
        assert is_contiguous_span(raw_tokens, left), (rec["id"], rec["raw_lines"])  # one run of neighbouring tokens
        phrase = None
        for known in LANDMARK_TOKENS:
            if Counter(known.split()) == Counter(t.casefold() for t in left.elements()):
                phrase = known
        assert phrase, (rec["id"], dict(left))  # and it is one of the known landmark phrases, nothing else
    assert not any("landmark" in r["tags"] for r in by_country["IN"] if r["difficulty"] != "hard")


def test_landmark_text_is_never_in_gold(by_country):
    for rec in by_country["IN"]:
        if "landmark" in rec["tags"]:
            gold_text = " ".join(rec["gold"].values()).casefold()
            assert not any(word in gold_text for word in ("near ", "opp.", "behind ", "next to", "opposite "))


def test_a_non_landmark_record_has_no_unexplained_token(by_country):
    for rec in by_country["IN"]:
        if "landmark" not in rec["tags"]:
            gold = Counter(t for n, v in rec["gold"].items() if n != "Ctry" for t in v.split())
            rest = tokens(written_text(rec)) - gold
            assert sum(rest.values()) <= 1, (rec["id"], dict(rest))  # at most the one-word country


def test_long_addresses_are_common_and_split_across_lines(by_country):
    assert sum("long_line_split" in r["tags"] for r in by_country["IN"]) > 30
    assert max(len(r["raw_lines"]) for r in by_country["IN"]) >= 4


def test_only_the_listed_abbreviation_is_written(by_country):
    assert in_.India().abbreviation_tokens() == frozenset({"RD"})
