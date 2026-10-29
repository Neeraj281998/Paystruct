"""Netherlands (guide section 15)."""
from __future__ import annotations

import re

from addrgen.countries import nl
from tests.helpers import appears_in_order

RANGES = {t.casefold(): (lo, hi) for t, lo, hi in nl.TOWNS}
ENDINGS = tuple(e for e, _ in nl._ENDINGS)


def test_number_after_the_street_and_postcode_before_the_town(by_country):
    for rec in by_country["NL"]:
        if "BldgNb" in rec["gold"] and "StrtNm" in rec["gold"]:
            assert appears_in_order(rec, "StrtNm", "BldgNb"), rec["raw_lines"]
        if not {"reordered", "postcode_wrong_line", "postcode_split"} & set(rec["tags"]):
            assert appears_in_order(rec, "PstCd", "TwnNm"), rec["raw_lines"]


def test_postcode_is_four_digits_a_space_and_two_letters_inside_the_towns_range(by_country):
    for rec in by_country["NL"]:
        pc = rec["gold"]["PstCd"]
        if "postcode_no_space" in rec["tags"]:
            assert re.fullmatch(r"\d{4}[A-Z]{2}", pc), pc  # "1015CJ"
            number = int(pc[:4])
        else:
            assert re.fullmatch(r"\d{4} [A-Z]{2}", pc), pc
            number = int(pc[:4])
        lo, hi = RANGES[rec["gold"]["TwnNm"].casefold()]
        assert lo <= number <= hi, (rec["id"], pc)
        assert not set(pc[-2:]) & set("FIOQUY"), pc  # letters a Dutch postcode never uses


def test_postcode_no_space_and_split_both_happen(by_country):
    tags = {t for r in by_country["NL"] for t in r["tags"]}
    assert {"postcode_no_space", "postcode_split"} <= tags


def test_number_additions_stay_in_the_number(by_country):
    forms = set()
    for rec in by_country["NL"]:
        nb = rec["gold"].get("BldgNb")
        if nb:
            assert re.fullmatch(r"(?i)\d+([A-D]|-\d)?", nb), nb
            forms.add("letter" if re.search(r"[A-Za-z]", nb) else "dash" if "-" in nb else "plain")
    assert forms == {"letter", "dash", "plain"}


def test_street_names_are_compounds_ending_in_a_street_word(by_country):
    van = 0
    for rec in by_country["NL"]:
        street = rec["gold"].get("StrtNm")
        if street:
            assert street.split(" ")[-1].casefold().endswith(ENDINGS), street
            van += street.startswith(("Van ", "VAN "))
    assert van > 10


def test_no_abbreviations_are_generated_for_nl(by_country):
    assert not any("abbreviated" in r["tags"] for r in by_country["NL"])
    assert nl.Netherlands().abbreviation_tokens() == frozenset()


def test_rooms_floors_buildings_and_po_boxes(by_country):
    for rec in by_country["NL"]:
        gold = rec["gold"]
        if "PstBx" in gold:
            assert re.fullmatch(r"(?i)Postbus \d+", gold["PstBx"]) and "StrtNm" not in gold
        if "Flr" in gold:
            assert re.fullmatch(r"(?i)(\d+e etage|Begane grond)", gold["Flr"])
        if "Room" in gold:
            assert gold["Room"].split(" ")[0].casefold() in {"unit", "kamer"}


def test_no_region_and_no_locality(by_country):
    assert not any({"CtrySubDvsn", "TwnLctnNm"} & set(r["gold"]) for r in by_country["NL"])


def test_country_names_include_holland_and_the_netherlands(by_country):
    written = {t for r in by_country["NL"] if "country_name" in r["tags"] for line in r["raw_lines"] for t in [line]}
    assert any("Holland" in w or "HOLLAND" in w for w in written) and any("Netherlands" in w.title() for w in written)
