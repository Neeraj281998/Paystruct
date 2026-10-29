"""Postcode-to-town ties: every postcode written beside a town is one GeoNames lists for it (addrgen/data/postcode_ties.json,
built by scripts/build_postcode_ties.py). The last test re-checks the committed JSON against the GeoNames files when they
are present (they are not committed)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

from addrgen.countries import gb, in_, nl, us
from addrgen.ties import ties

REPO = Path(__file__).resolve().parents[3]
GEONAMES = REPO / "data" / "reference" / "geonames-postal"
T = ties()


def test_the_json_names_its_source_and_license():
    assert "GeoNames" in T["source"] and "CC BY 4.0" in T["source"]


def test_every_us_and_de_town_has_codes_and_no_repeats():
    for country in ("US", "DE"):
        for town, codes in T[country].items():
            assert len(codes) >= 8 and len(codes) == len(set(codes)) and all(re.fullmatch(r"\d{5}", c) for c in codes), town


def test_us_zip_is_one_listed_for_the_city(by_country):
    for rec in by_country["US"]:
        g = rec["gold"]
        assert g["PstCd"][:5] in {z for c in us.CITIES if c[0].casefold() == g["TwnNm"].casefold() for z in c[3]}


def test_the_old_wrong_suburban_zips_are_gone(by_country):
    """The first tables tied Philadelphia to 190xx (Villanova is 19085) and Seattle to 980xx (Ravensdale is 98051)."""
    for rec in by_country["US"]:
        g = rec["gold"]
        if g["TwnNm"] == "Philadelphia":
            assert g["PstCd"].startswith("191"), rec["id"]
        if g["TwnNm"] == "Seattle":
            assert g["PstCd"].startswith("981"), rec["id"]


def _in_key(town):  # gold keeps the case written, so ALL CAPS records need the table's spelling
    return next(t for t in T["IN"]["cities"] if t.casefold() == town.casefold())


def test_in_pin_is_listed_for_the_city_and_has_the_cities_prefix(by_country):
    prefixes = {c[0]: c[2] for c in in_.CITIES}
    for rec in by_country["IN"]:
        g = rec["gold"]
        town = _in_key(g["TwnNm"])
        pin = g["PstCd"].replace(" ", "")
        assert pin in T["IN"]["cities"][town] and pin.startswith(prefixes[town]), rec["id"]


def test_in_locality_is_written_with_its_own_pin_when_known(by_country):
    tied = sectors = 0
    for rec in by_country["IN"]:
        g = rec["gold"]
        pin, loc = g["PstCd"].replace(" ", ""), g.get("TwnLctnNm")
        if not loc:
            continue
        town = _in_key(g["TwnNm"])
        loc_key = next((k for k in T["IN"]["localities"] if k.casefold() == f"{town}|{loc}".casefold()), None)
        m = re.fullmatch(r"sector (\d+)", loc.casefold())
        if m:
            sectors += 1
            assert T["IN"]["sectors"][town][m.group(1)] == pin, rec["id"]
        elif loc_key:
            tied += 1
            assert pin in T["IN"]["localities"][loc_key]["pins"], rec["id"]
    assert tied > 100 and sectors > 20


def test_sectors_exist_only_for_cities_with_a_listed_pin():
    for town, mapping in T["IN"]["sectors"].items():
        assert mapping and all(pin in T["IN"]["cities"][town] for pin in mapping.values())
    assert max(map(int, T["IN"]["sectors"]["Chandigarh"])) < 62  # Chandigarh has about 61 sectors


def test_dwarka_is_tied_to_a_dwarka_pin():
    assert "110007" not in T["IN"]["localities"]["New Delhi|Dwarka"]["pins"]
    assert "110075" in T["IN"]["localities"]["New Delhi|Dwarka"]["pins"]


def test_gb_locality_is_written_with_an_outward_code_listed_for_it(by_country):
    tied = 0
    for rec in by_country["GB"]:
        g = rec["gold"]
        if "TwnLctnNm" not in g:
            continue
        wanted = f"{g['TwnNm']}|{g['TwnLctnNm']}".casefold()  # the town may be written in capitals
        key = next((k for k in T["GB"]["localities"] if k.casefold() == wanted), None)
        if key:
            tied += 1
            assert g["PstCd"].replace(" ", "")[:-3] in T["GB"]["localities"][key], rec["id"]
    assert tied > 30


def test_gb_every_town_still_gets_a_code_of_its_own_area(by_country):
    areas = {t[0].casefold(): {re.match(r"[A-Z]+", o).group() for o in t[1]} for t in gb.POST_TOWNS}
    areas["london"] |= {"E", "EC", "N", "NW", "SE", "SW", "W", "WC"}
    for rec in by_country["GB"]:
        g = rec["gold"]
        assert re.match(r"[A-Z]+", g["PstCd"]).group() in areas[g["TwnNm"].casefold()], rec["id"]


def test_nl_never_writes_1099_for_amsterdam(by_country):
    assert dict((t, hi) for t, _, hi in nl.TOWNS)["Amsterdam"] == 1098
    assert not any(r["gold"]["PstCd"].startswith("1099") for r in by_country["NL"])


def test_unconfirmed_pairings_are_listed():
    u = T["unconfirmed"]
    assert set(u) == {"IN_locality_pin_from_memory", "IN_locality_without_pin_tie", "GB_locality_without_outward_tie"}
    assert all(isinstance(v, list) and v for v in u.values())


@pytest.mark.skipif(not GEONAMES.exists(), reason="GeoNames files are not committed (data/reference/)")
def test_committed_ties_agree_with_the_geonames_files():
    sys.path.insert(0, str(REPO / "scripts"))
    import audit_postcode_ties as audit

    for country, key in (("US", "US"), ("DE", "DE")):
        data = audit.load(country)
        for town, codes in T[key].items():
            state = next((c[1] for c in us.CITIES if c[0] == town), None)
            for code in codes:
                assert any(audit.row_is_town(country, town, state, r) for r in data[code]), (town, code)
    data = audit.load("IN")
    for town, pins in T["IN"]["cities"].items():
        state = next(c[1] for c in in_.CITIES if c[0] == town)
        for pin in pins:
            assert any(audit.row_is_town("IN", town, state, r) for r in data[pin]), (town, pin)
