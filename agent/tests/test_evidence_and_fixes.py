"""Confidence by evidence, and the four pattern fixes of the audit round. Written from pattern descriptions."""
import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from agent.rules.engine import RulesEngine, load_config
from agent.rules.state import ACCEPT, ELIMINATION, EXPLICIT, NEEDS_LLM

from .conftest import make_gazetteer
from .test_properties import ENGINE, hints, lines_random, lines_words

CAP = load_config()["signals"]["elimination_cap"]
ACCEPT_AT = load_config()["thresholds"]["accept"]


def parse(engine, lines, hint=None):
    return engine.parse(lines, hint)


def test_the_elimination_cap_is_below_the_accept_threshold():
    assert CAP < ACCEPT_AT


# -- 1. confidence by evidence: one test per rule that can set a field by elimination ----------------------------------
def test_locality_not_in_the_gazetteer_is_elimination_and_cannot_be_accepted(engine):
    r = parse(engine, ["12 Main St", "Zorbleville", "Cork T12 AC34", "IE"])
    assert r.fields["TwnLctnNm"] == "Zorbleville" and r.field_basis["TwnLctnNm"] == ELIMINATION
    assert r.field_confidence["TwnLctnNm"] <= CAP and r.route == NEEDS_LLM and "by_elimination:TwnLctnNm" in r.route_reasons


def test_locality_listed_in_the_gazetteer_is_explicit(engine):
    r = parse(engine, ["12 Main St", "Templeogue", "Dublin 6W", "D6W 5D75", "IE"])
    assert r.fields["TwnLctnNm"] == "Templeogue" and r.field_basis["TwnLctnNm"] == EXPLICIT and r.route == ACCEPT


def test_locality_matching_a_profile_pattern_is_explicit(engine):
    r = parse(engine, ["Plot 80, Tilka Lane", "Sector 40", "Pune, Maharashtra 411001", "IN"])
    assert r.field_basis["TwnLctnNm"] == EXPLICIT and r.route == ACCEPT


def test_street_name_after_a_number_with_no_street_word_is_elimination(engine):
    r = parse(engine, ["14 Zorble", "Cork T12 AC34", "IE"])
    assert r.fields["StrtNm"] == "Zorble" and r.field_basis["StrtNm"] == ELIMINATION and r.route == NEEDS_LLM


def test_dutch_name_before_a_number_with_no_street_word_is_elimination(engine):
    r = parse(engine, ["Zorble 14", "3511 ED Utrecht", "NL"])
    assert r.field_basis.get("StrtNm") == ELIMINATION and r.route == NEEDS_LLM


def test_a_street_holding_an_unrecognised_digit_token_is_elimination(engine):
    r = parse(engine, ["Prinsengracht 263-II", "1016 GV Amsterdam", "NL"])
    assert r.field_basis["StrtNm"] == ELIMINATION and r.route == NEEDS_LLM


def test_ordinals_inside_a_street_are_fine(engine):
    for lines in (["19 5th Main Road", "Pune, Maharashtra 411001", "IN"], ["210 W 5th Street", "Austin, TX 78701", "US"]):
        r = parse(engine, lines)
        assert r.field_basis["StrtNm"] == EXPLICIT and r.route == ACCEPT


def test_a_town_the_gazetteer_lacks_is_elimination(engine):
    r = parse(engine, ["12 Main St", "Ballyvaughan", "H91 W3R7", "IE"])
    assert r.fields["TwnNm"] == "Ballyvaughan" and r.field_basis["TwnNm"] == ELIMINATION and r.route == NEEDS_LLM


@pytest.mark.parametrize("lines", [
    ["Flat 2, 14 Marlow Court", "Bristol BS6 7QD", "UK"],
    ["Ground Floor", "PO Box 12", "Cork T12 AC34", "IE"],
    ["64B Market Square", "Kilkenny R95 NRC2", "Co. Kilkenny", "Ireland"],
    ["32 BIS RUE DU CHÂTEAU", "13016 MARSEILLE 16E, FR"],
])
def test_fields_set_by_a_keyword_pattern_gazetteer_or_profile_word_are_explicit(engine, lines):
    r = parse(engine, lines)
    assert set(r.field_basis.values()) == {EXPLICIT} and r.route == ACCEPT


def test_unknown_words_lower_confidence_and_go_to_the_llm(engine):
    r = parse(engine, ["Zorb 12, Flurble Bldg", "Gt. Western Rd", "Swindon SN1 1AA", "UK"])
    assert r.route == NEEDS_LLM
    r = parse(engine, ["Rm 12", "Mulberry Hall", "14 Zorble", "Cork T12 AC34", "IE"])
    assert r.route == NEEDS_LLM


def test_unlisted_and_unrecognised_never_reaches_accept(engine):
    # an unlisted locality AND an unrecognised leftover word
    r = parse(engine, ["12 Main St", "Zorbleville", "qwxz", "Cork T12 AC34", "IE"])
    assert r.route != ACCEPT


SETTINGS = settings(max_examples=250, deadline=None, suppress_health_check=[HealthCheck.too_slow])


@SETTINGS
@given(lines=st.one_of(lines_random, lines_words), hint=hints)
def test_no_address_with_an_elimination_field_is_ever_accepted(lines, hint):
    r = ENGINE.parse(lines, hint)
    elim = [n for n, how in r.field_basis.items() if how == ELIMINATION]
    if elim:
        assert r.route != ACCEPT, (lines, elim)
        assert all(r.field_confidence[n] <= CAP for n in elim)
    assert set(r.field_basis) <= set(r.fields)


@SETTINGS
@given(parts=st.lists(st.sampled_from(["Zorble", "Flurb", "Mary's", "Gate", "Wynd", "12", "Cork", "T12", "AC34", "IE", "Co.", "Kerry", "Sector"]),
                      min_size=1, max_size=9))
def test_accept_needs_every_field_explicit_on_vocabulary_that_is_partly_unknown(parts):
    r = ENGINE.parse([" ".join(parts)])
    if r.route == ACCEPT:
        assert ELIMINATION not in r.field_basis.values()


# -- 2. Sector / Sec ----------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("sector", ["Sector 12", "Sec 12", "Sector-12", "Sec. 12", "sector 12", "SECTOR 12"])
def test_sector_is_a_locality_not_a_house_number(engine, sector):
    r = parse(engine, ["Plot 5, Mill Road", sector, "Noida, Uttar Pradesh 201301", "India"])
    assert r.fields["TwnLctnNm"].lower().replace(" ", "").replace(".", "") in {"sector12", "sec12", "sector-12"} and r.fields["BldgNb"] == "Plot 5"
    assert r.field_basis["TwnLctnNm"] == EXPLICIT


def test_sector_alone_does_not_invent_a_house_number(engine):
    r = parse(engine, ["Mill Road, Sector 12", "Noida, Uttar Pradesh 201301", "India"])
    assert "BldgNb" not in r.fields and r.fields["TwnLctnNm"] == "Sector 12" and r.fields["StrtNm"] == "Mill Road"


def test_sector_with_a_letter_suffix(engine):
    r = parse(engine, ["SCO 118, Sector 17-C", "Chandigarh 160017", "India"])
    assert r.fields["TwnLctnNm"] == "Sector 17-C"


# -- 3. city name equal to a state name --------------------------------------------------------------------------------
@pytest.mark.parametrize("lines", [
    ["12 Elm St", "New York NY 10001"],
    ["12 Elm St", "New York, NY 10001", "US"],
    ["12 Elm St", "New York, New York 10001", "US"],
    ["12 Elm St", "10001 New York NY", "US"],
])
def test_town_first_then_the_written_state(engine, lines):
    r = parse(engine, lines, hint="US")
    assert r.fields["TwnNm"] == "New York" and r.fields["CtrySubDvsn"].lower() in {"ny", "new york"}
    assert r.fields["TwnNm"] != r.fields.get("CtrySubDvsn") or lines[1].count("New York") == 2


def test_town_name_equal_to_a_state_with_no_state_written_is_just_a_town(engine):
    r = parse(engine, ["12 Elm St", "New York 10001"], hint="US")
    assert r.fields["TwnNm"] == "New York" and "CtrySubDvsn" not in r.fields


def test_washington_dc_is_unchanged(engine):
    r = parse(engine, ["1600 Pennsylvania Ave NW", "Washington DC 20500"], hint="US")
    assert r.fields["TwnNm"] == "Washington" and r.fields["CtrySubDvsn"] == "DC"


# -- 4. Canadian street-type clash --------------------------------------------------------------------------------------
@pytest.mark.parametrize("street", ["Williams Boulevard", "Park Place", "Queen Avenue"])
def test_a_town_after_an_english_street_type_is_a_town(engine, street):
    r = parse(engine, [f"721 {street} Winnipeg Manitoba R3C 4X7 CA"])
    assert r.fields["TwnNm"] == "Winnipeg" and r.fields["StrtNm"] == street and "street_town_clash" not in r.flags
    assert r.route == ACCEPT


def test_a_french_type_first_street_keeps_its_name_out_of_the_town(engine):
    r = parse(engine, ["492 Boulevard Notre-Dame", "Québec QC G1V 3G5", "CA"])
    assert r.fields["StrtNm"] == "Boulevard Notre-Dame" and r.fields["TwnNm"] == "Québec"


def test_an_unclear_clash_goes_to_the_llm(engine):
    # "Boulevard Winnipeg" could be a French street name, or a street type then a town
    r = parse(engine, ["25 Boulevard Winnipeg Manitoba R3C 4X7 CA"])
    assert "street_town_clash" in r.flags and r.route == NEEDS_LLM


def test_court_is_an_english_type_only(engine):
    r = parse(engine, ["9 Maple Court Winnipeg Manitoba R3C 4X7 CA"])
    assert r.fields["TwnNm"] == "Winnipeg" and r.fields["StrtNm"] == "Maple Court" and r.route == ACCEPT


def test_the_same_word_in_a_pure_type_first_country_still_excludes(engine):
    r = parse(engine, ["12 Rue Paris", "75001 Lyon", "FR"])
    assert r.fields["TwnNm"] == "Lyon"


# -- 5. entries that came from the hard set are gone --------------------------------------------------------------------
def test_hard_set_derived_profile_entries_were_removed(ctx):
    fr, in_ = ctx.profiles["FR"], ctx.profiles["IN"]
    assert "rés" not in fr.building_words and "résid" not in fr.building_words and "res" not in fr.building_words
    assert not in_.landmark_suffixes
    assert not any(p.fullmatch("New No. 12") or p.fullmatch("H.No. 1182") for p in in_.bldgnb_patterns)
