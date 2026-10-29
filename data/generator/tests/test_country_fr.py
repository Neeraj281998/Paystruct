"""France (guide section 13)."""
from __future__ import annotations

import re

from addrgen.countries import fr
from tests.helpers import appears_in_order, written_text

ARR_PREFIX = {t.casefold(): prefix for t, prefix, _ in fr.ARRONDISSEMENT_TOWNS}
PLAIN = {t.casefold(): set(codes) for t, codes in fr.PLAIN_TOWNS}


def test_number_before_street_and_the_street_word_first(by_country):
    for rec in by_country["FR"]:
        gold = rec["gold"]
        if "BldgNb" in gold and "StrtNm" in gold:
            assert appears_in_order(rec, "BldgNb", "StrtNm"), rec["raw_lines"]
        if "StrtNm" in gold:
            assert gold["StrtNm"].split(" ")[0].rstrip(".").casefold() in fr.France.street_words, gold["StrtNm"]


def test_postcode_comes_before_the_town_unless_reordered(by_country):
    checked = 0
    for rec in by_country["FR"]:
        if {"reordered", "postcode_wrong_line", "postcode_split"} & set(rec["tags"]):
            continue
        checked += 1
        assert appears_in_order(rec, "PstCd", "TwnNm"), rec["raw_lines"]
    assert checked > 300


def test_cedex_stays_with_the_town_and_is_tagged(by_country):
    cedex = [r for r in by_country["FR"] if "cedex" in r["tags"]]
    assert len(cedex) > 20
    for rec in cedex:
        assert re.fullmatch(r"(?i)[^ ]+( [^ ]+)* cedex \d{2}", rec["gold"]["TwnNm"]) and rec["difficulty"] == "hard"
        assert re.fullmatch(r"\d{5}", rec["gold"]["PstCd"])  # the postcode stays five digits, without the Cedex
    assert not any("cedex" in r["gold"]["TwnNm"].casefold() for r in by_country["FR"] if "cedex" not in r["tags"])


def test_an_arrondissement_written_with_the_town_matches_the_postcode(by_country):
    found = 0
    for rec in by_country["FR"]:
        m = re.fullmatch(r"(?i)(paris|lyon|marseille) (\d+)(?:e|er)", rec["gold"]["TwnNm"])
        if m:
            found += 1
            assert "postal_district" in rec["tags"]
            assert rec["gold"]["PstCd"] == f"{ARR_PREFIX[m.group(1).casefold()]}{int(m.group(2)):02d}"  # Paris 8e is 75008
    assert found > 20
    assert not any("postal_district" in r["tags"] for r in by_country["FR"] if r["difficulty"] != "hard")


def test_postcodes_belong_to_their_town(by_country):
    for rec in by_country["FR"]:
        town = re.sub(r"(?i)( cedex \d+)?( \d+(e|er))?$", "", rec["gold"]["TwnNm"]).casefold()
        code = rec["gold"]["PstCd"]
        if town in ARR_PREFIX:
            assert code.startswith(ARR_PREFIX[town]), (rec["id"], town, code)
        else:
            assert code in PLAIN[town], (rec["id"], town, code)


def test_no_region_and_no_locality_is_ever_written(by_country):
    assert not any({"CtrySubDvsn", "TwnLctnNm"} & set(r["gold"]) for r in by_country["FR"])


def test_floors_rooms_buildings_and_po_boxes_use_french_words(by_country):
    seen = set()
    for rec in by_country["FR"]:
        gold = rec["gold"]
        if "Room" in gold:
            seen.add(gold["Room"].split(" ")[0].casefold().rstrip("."))
        if "PstBx" in gold:
            assert re.fullmatch(r"(?i)BP \d+", gold["PstBx"]) and "StrtNm" not in gold
        if "BldgNm" in gold:
            assert gold["BldgNm"].split(" ")[0].casefold() in fr.France.building_word_set
    assert {"appartement", "bureau", "appt"} & seen


def test_accents_are_kept_and_all_caps_keeps_them(by_country):
    towns = {r["gold"]["TwnNm"] for r in by_country["FR"]}
    assert towns & {"Nîmes", "Orléans", "Besançon"} and towns & {"NÎMES", "ORLÉANS", "BESANÇON"}


def test_only_the_listed_abbreviations_are_written(by_country):
    allowed = {"AV", "BD", "PL", "CH", "IMP", "ALL", "APPT"}
    used = set()
    for rec in by_country["FR"]:
        if "abbreviated" in rec["tags"]:
            used |= {w.rstrip(".").upper() for f in ("StrtNm", "Room") for w in rec["gold"].get(f, "").split()} & allowed
    assert used  # abbreviations happen
    assert fr.France().abbreviation_tokens() == frozenset(allowed)


def test_a_street_written_in_full_is_never_abbreviated_unless_tagged(by_country):
    for rec in by_country["FR"]:
        if "abbreviated" not in rec["tags"] and "StrtNm" in rec["gold"]:
            assert rec["gold"]["StrtNm"].split(" ")[0].rstrip(".").casefold() not in {"av", "bd", "pl", "ch", "imp", "all"}
