"""United States (guide section 17)."""
from __future__ import annotations

import re

from addrgen.countries import us
from tests.helpers import appears_in_order, written_text

CITIES = {c[0].casefold(): c for c in us.CITIES}


def test_state_matches_the_town_and_the_zip_prefix(by_country):
    for rec in by_country["US"]:
        gold = rec["gold"]
        _, code, name, prefixes = CITIES[gold["TwnNm"].casefold()]
        assert gold["CtrySubDvsn"].casefold() in {code.casefold(), name.casefold()}, rec["id"]
        assert gold["PstCd"][:3] in prefixes, rec["id"]


def test_zip_and_zip_plus_four_keep_their_hyphen(by_country):
    plain = plus4 = 0
    for rec in by_country["US"]:
        pc = rec["gold"]["PstCd"]
        assert re.fullmatch(r"\d{5}(-\d{4})?", pc), pc
        plus4 += "-" in pc
        plain += "-" not in pc
        assert pc in written_text(rec)  # the hyphen is in the text too
    assert plain > 400 and plus4 > 50


def test_city_state_zip_in_natural_order(by_country):
    for rec in by_country["US"]:
        if not {"reordered", "postcode_wrong_line"} & set(rec["tags"]):
            assert appears_in_order(rec, "TwnNm", "CtrySubDvsn") and appears_in_order(rec, "CtrySubDvsn", "PstCd"), rec["raw_lines"]


def test_the_comma_after_the_city_is_written_unless_commas_are_missing(by_country):
    with_comma = [r for r in by_country["US"] if "missing_commas" not in r["tags"] and "reordered" not in r["tags"]
                  and "one_line" not in r["tags"] and "postcode_wrong_line" not in r["tags"]]
    assert with_comma
    hits = [r for r in with_comma if re.search(re.escape(r["gold"]["TwnNm"]) + r"\s*,", "\n".join(r["raw_lines"]))]
    assert len(hits) > 0.8 * len(with_comma)
    assert all("," not in "\n".join(r["raw_lines"]) for r in by_country["US"] if "missing_commas" in r["tags"])


def test_directionals_stay_in_the_street_name(by_country):
    streets = [r["gold"]["StrtNm"] for r in by_country["US"] if "StrtNm" in r["gold"] and "all_caps" not in r["tags"]]
    assert any(re.match(r"[NSEW] ", s) for s in streets) and any(re.search(r" (NW|NE|SW|SE)$", s) for s in streets)


def test_court_and_way_are_street_words_here(by_country):
    last = {r["gold"]["StrtNm"].split(" ")[-1].rstrip(".") for r in by_country["US"] if "StrtNm" in r["gold"]}
    assert {"Court", "Way"} & last or {"Ct"} & last


def test_units_keep_their_keyword_or_hash(by_country):
    forms = set()
    for rec in by_country["US"]:
        room = rec["gold"].get("Room")
        if room and "all_caps" not in rec["tags"]:
            forms.add("#" if room.startswith("#") else room.split(" ")[0].rstrip("."))
    assert {"#", "Suite", "Unit"} <= forms and forms & {"Apartment", "Apt"}


def test_floor_forms_and_po_box_forms(by_country):
    floors, boxes = set(), set()
    for rec in by_country["US"]:
        gold = rec["gold"]
        if "Flr" in gold and "all_caps" not in rec["tags"]:
            floors.add("Fl" if gold["Flr"].startswith("Fl ") else "Floor")
        if "PstBx" in gold:
            assert "StrtNm" not in gold
            boxes.add(gold["PstBx"].split(" ")[0].upper())
    assert floors == {"Fl", "Floor"} and {"PO", "P.O."} <= boxes


def test_every_country_name_form_is_written(by_country):
    seen = set()
    for rec in by_country["US"]:
        if "country_name" in rec["tags"]:
            text = "\n".join(rec["raw_lines"]).upper()
            seen |= {n for n in ("U.S.A.", "UNITED STATES OF AMERICA", "UNITED STATES", "USA") if n in text}
    assert {"U.S.A.", "UNITED STATES OF AMERICA", "USA"} <= seen
    assert any(r["raw_lines"][-1].strip().rstrip(",") == "US" for r in by_country["US"] if "country_name" not in r["tags"]
               and "no_country" not in r["tags"])


def test_no_locality_and_no_postcode_split_or_space_drop(by_country):
    for rec in by_country["US"]:
        assert "TwnLctnNm" not in rec["gold"]
        assert not {"postcode_split", "postcode_no_space"} & set(rec["tags"])


def test_only_the_listed_abbreviations_are_written(by_country):
    allowed = {"ST", "AVE", "BLVD", "DR", "LN", "RD", "CT", "PL", "PKWY", "CIR", "TRL", "HWY", "APT", "STE"}
    assert us.UnitedStates().abbreviation_tokens() == frozenset(allowed)
