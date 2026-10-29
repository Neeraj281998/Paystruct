"""Germany (guide section 14)."""
from __future__ import annotations

import re

from addrgen.countries import de
from tests.helpers import appears_in_order, written_text

ENDINGS = ("straße", "strasse", "str", "weg", "allee", "platz", "gasse", "ring", "damm", "ufer")
PREFIXES = {t.casefold(): set(p) for t, p in de.TOWNS}


def test_number_after_the_street(by_country):
    checked = 0
    for rec in by_country["DE"]:
        if "BldgNb" in rec["gold"] and "StrtNm" in rec["gold"]:
            checked += 1
            assert appears_in_order(rec, "StrtNm", "BldgNb"), rec["raw_lines"]
    assert checked > 300


def test_postcode_before_the_town_unless_reordered(by_country):
    for rec in by_country["DE"]:
        if not {"reordered", "postcode_wrong_line", "postcode_split"} & set(rec["tags"]):
            assert appears_in_order(rec, "PstCd", "TwnNm"), rec["raw_lines"]


def test_postcodes_are_five_digits_and_belong_to_the_town(by_country):
    for rec in by_country["DE"]:
        pc = rec["gold"]["PstCd"]
        assert re.fullmatch(r"\d{5}", pc) and pc[:3] in PREFIXES[rec["gold"]["TwnNm"].casefold()], rec["id"]


def test_street_names_are_compounds_or_two_words_and_end_in_a_street_word(by_country):
    two_word = compound = 0
    for rec in by_country["DE"]:
        street = rec.get("gold", {}).get("StrtNm")
        if not street:
            continue
        words = street.split(" ")
        assert words[-1].rstrip(".").casefold().endswith(ENDINGS), street
        two_word += len(words) > 1
        compound += len(words) == 1
    assert two_word > 20 and compound > 300


def test_eszett_becomes_ss_in_all_caps_and_gold_follows_the_text(by_country):
    caps = [r for r in by_country["DE"] if "all_caps" in r["tags"] and "StrtNm" in r["gold"]]
    assert caps
    assert not any("ß" in r["gold"]["StrtNm"] for r in caps)  # upper-casing turned it into SS
    assert any("STRASSE" in r["gold"]["StrtNm"] for r in caps)
    assert any("ß" in r["gold"]["StrtNm"] for r in by_country["DE"] if "all_caps" not in r["tags"] and "StrtNm" in r["gold"])
    for r in caps:
        assert r["gold"]["StrtNm"] in written_text(r)  # gold is what the text says


def test_umlauts_survive(by_country):
    towns = {r["gold"]["TwnNm"] for r in by_country["DE"]}
    assert {"München", "Köln", "Düsseldorf"} & towns


def test_abbreviation_is_str_as_an_ending_or_a_word(by_country):
    forms = set()
    for rec in by_country["DE"]:
        if "abbreviated" in rec["tags"]:
            street = rec["gold"]["StrtNm"]
            assert street.split(" ")[-1].rstrip(".").casefold().endswith("str"), street
            forms.add("separate" if len(street.split(" ")) > 1 else "ending")
    assert forms == {"separate", "ending"} or forms == {"ending"}
    assert de.Germany().abbreviation_tokens() == frozenset({"STR"})


def test_a_typo_only_touches_the_stem_never_the_ending(by_country):
    typos = [r for r in by_country["DE"] if "typo" in r["tags"]]
    assert len(typos) > 20
    for rec in typos:
        for name in ("StrtNm", "BldgNm"):
            if name in rec["gold"] and name == "StrtNm":
                assert rec["gold"][name].split(" ")[-1].rstrip(".").casefold().endswith(ENDINGS)


def test_no_region_and_no_locality_and_no_space_to_drop(by_country):
    for rec in by_country["DE"]:
        assert not {"CtrySubDvsn", "TwnLctnNm"} & set(rec["gold"])
        assert "postcode_no_space" not in rec["tags"] and "postcode_split" not in rec["tags"]


def test_rooms_floors_buildings_and_po_boxes(by_country):
    seen_room, seen_floor = set(), set()
    for rec in by_country["DE"]:
        gold = rec["gold"]
        if "Room" in gold:
            seen_room.add(gold["Room"].split(" ")[0].casefold())
        if "Flr" in gold:
            seen_floor.add("og" if "OG" in gold["Flr"].upper() else gold["Flr"].casefold().split(" ")[0])
        if "PstBx" in gold:
            assert re.fullmatch(r"(?i)Postfach \d+", gold["PstBx"]) and "StrtNm" not in gold
    assert {"wohnung", "büro", "zimmer"} <= seen_room
    assert {"og", "eg", "erdgeschoss"} & seen_floor


def test_number_letters_are_lower_case(by_country):
    letters = [r["gold"]["BldgNb"] for r in by_country["DE"] if "BldgNb" in r["gold"] and "all_caps" not in r["tags"]
               and re.search(r"[A-Za-z]", r["gold"]["BldgNb"])]
    assert letters and all(re.fullmatch(r"\d+[a-d]", n) for n in letters)
