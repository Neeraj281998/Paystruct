"""Canada (guide section 16)."""
from __future__ import annotations

import re

from addrgen.countries import ca
from tests.helpers import appears_in_order

TOWNS = {t[0].casefold(): t for t in ca.TOWNS}
FIRST_LETTER = {"ON": "KLMNP", "QC": "GHJ", "BC": "V", "AB": "T", "MB": "R", "SK": "S", "NS": "B", "NB": "E", "NL": "A", "PE": "C"}
FR_TYPES = {w for w, _ in ca._FR_TYPES}


def test_province_is_always_written_and_matches_the_postcode_and_town(by_country):
    for rec in by_country["CA"]:
        gold = rec["gold"]
        _, code, name, fsas, _ = TOWNS[gold["TwnNm"].casefold()]
        assert gold["CtrySubDvsn"].casefold() in {code.casefold(), name.casefold()}, rec["id"]
        assert gold["PstCd"].replace(" ", "")[:3].upper() in fsas, rec["id"]
        assert gold["PstCd"].replace(" ", "")[0].upper() in FIRST_LETTER[code], rec["id"]


def test_the_province_is_written_as_a_code_and_as_a_name(by_country):
    written = {r["gold"]["CtrySubDvsn"] for r in by_country["CA"] if "all_caps" not in r["tags"]}
    assert {"ON", "Ontario"} <= written and {"QC", "Québec"} <= written


def test_postal_code_format_and_the_letters_it_never_uses(by_country):
    for rec in by_country["CA"]:
        pc = rec["gold"]["PstCd"]
        compact = pc.replace(" ", "")
        assert re.fullmatch(r"[A-Z]\d[A-Z]\d[A-Z]\d", compact), pc
        assert not set(compact[3:]) & set("DFIOQU"), pc  # D, F, I, O, Q, U never appear
        assert compact[0] not in "WZ", pc
        assert (" " not in pc) == ("postcode_no_space" in rec["tags"]), pc


def test_postcode_follows_the_province_in_natural_order(by_country):
    for rec in by_country["CA"]:
        if not {"reordered", "postcode_wrong_line", "postcode_split"} & set(rec["tags"]):
            assert appears_in_order(rec, "TwnNm", "CtrySubDvsn") and appears_in_order(rec, "CtrySubDvsn", "PstCd"), rec["raw_lines"]


def test_french_towns_write_french_streets_and_english_towns_english_ones(by_country):
    french = english = 0
    for rec in by_country["CA"]:
        street = rec["gold"].get("StrtNm")
        if not street:
            continue
        is_french_town = TOWNS[rec["gold"]["TwnNm"].casefold()][4]
        first = street.split(" ")[0].casefold()
        if is_french_town:
            french += 1
            assert first in {t.casefold() for t in FR_TYPES}, street  # the type comes first, in lower case in the source
        else:
            english += 1
            assert first not in {t.casefold() for t in FR_TYPES}, street
    assert french > 80 and english > 200
    assert 0.15 < french / (french + english) < 0.35  # about a quarter of CA streets are French


def test_french_street_types_are_written_in_lower_case_in_plain_text(by_country):
    plain = [r["gold"]["StrtNm"] for r in by_country["CA"] if "StrtNm" in r["gold"] and "all_caps" not in r["tags"]
             and TOWNS[r["gold"]["TwnNm"].casefold()][4]]
    assert plain and all(s.split(" ")[0].islower() for s in plain)


def test_directionals_stay_in_the_street_name(by_country):
    streets = [r["gold"]["StrtNm"] for r in by_country["CA"] if "StrtNm" in r["gold"] and "all_caps" not in r["tags"]]
    assert any(re.search(r" (West|East|W|E|Ouest|Est|O)$", s) for s in streets)


def test_court_is_a_street_word_here(by_country):
    words = {w.rstrip(".") for r in by_country["CA"] for w in r["gold"].get("StrtNm", "").split()}
    assert {"Court", "Ct"} & words


def test_no_hyphenated_unit_number_is_generated(by_country):
    assert not any("-" in r["gold"].get("BldgNb", "") for r in by_country["CA"])


def test_units_floors_buildings_and_po_boxes(by_country):
    keywords, floors, po = set(), set(), set()
    for rec in by_country["CA"]:
        gold = rec["gold"]
        if "Room" in gold:
            keywords.add(gold["Room"].split(" ")[0].casefold())
        if "Flr" in gold:
            floors.add("fr" if "tage" in gold["Flr"].casefold() or "é" in gold["Flr"].casefold() else "en")
        if "PstBx" in gold:
            po.add(gold["PstBx"].split(" ")[0].upper().rstrip("."))
            assert "StrtNm" not in gold
    assert {"unit", "suite", "app.", "bureau"} <= keywords | {"ste"}
    assert floors == {"en", "fr"} and {"PO", "C.P"} <= po


def test_ca_in_the_text_is_a_province_only_in_a_us_address_never_here(by_country):
    assert all(r["gold"]["Ctry"] == "CA" for r in by_country["CA"])
    assert not any(r["gold"]["CtrySubDvsn"].upper() == "CA" for r in by_country["CA"])  # California is not a Canadian province


def test_only_the_listed_abbreviations_are_written(by_country):
    allowed = {"ST", "AVE", "RD", "DR", "LN", "CRES", "BLVD", "CT", "PL", "STE"}
    assert ca.Canada().abbreviation_tokens() == frozenset(allowed)
    for rec in by_country["CA"]:
        if "abbreviated" in rec["tags"]:
            words = {w.rstrip(".").upper() for f in ("StrtNm", "Room") for w in rec["gold"].get(f, "").split()}
            assert words & allowed
