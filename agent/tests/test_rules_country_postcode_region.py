import pytest

from agent.rules.state import ParseState


def ctry(run, lines, hint=None):
    s = run(lines, "country", hint)
    return s.country, s.country_source, s


# -- country ---------------------------------------------------------------------------------------------------------
def test_explicit_iso_code_at_the_end(run):
    assert ctry(run, ["12 Main St, Cork T12 AC34, IE"])[:2] == ("IE", "code")


def test_country_name_in_the_local_language_and_in_english(run):
    assert ctry(run, ["Hauptstraße 5", "10115 Berlin", "Deutschland"])[0] == "DE"
    assert ctry(run, ["Keizersgracht 9", "1015 CJ Amsterdam", "Holland"])[0] == "NL"
    assert ctry(run, ["5 Rue X", "75008 Paris", "France"])[:2] == ("FR", "name")


def test_postcode_pattern_unique_to_one_country(run):
    assert ctry(run, ["10 Elm Way", "Bristol BS6 7QD"])[:2] == ("GB", "pattern")
    assert ctry(run, ["10 Elm Way", "Halifax NS B3H 2R6"])[0] == "CA"
    assert ctry(run, ["Kanaalstraat 88A", "2011VK Haarlem"])[0] == "NL"


def test_hint_is_the_fallback(run):
    country, source, _ = ctry(run, ["somewhere"], hint="FR")
    assert (country, source) == ("FR", "hint")


def test_nothing_to_go_on_gives_no_country(run):
    country, _, s = ctry(run, ["asdf qwer"])
    assert country is None and "Ctry" not in s.fields and "no_country" in s.flags


def test_CA_inside_a_us_address_is_california_not_canada(run):
    country, source, s = ctry(run, ["450 Larkspur Ave", "Pasadena, CA 91101"], hint="US")
    assert country == "US" and "country_conflict" not in s.flags
    country, _, _ = ctry(run, ["450 Larkspur Ave", "Pasadena, CA 91101", "US"])
    assert country == "US"


def test_CA_at_the_end_after_a_canadian_postcode_is_canada(run):
    assert ctry(run, ["88 Tamarack Crescent", "Halifax, NS B3H 2R6, CA"])[:2] == ("CA", "code")


def test_a_us_state_code_that_is_also_a_country_code_is_a_state(run):
    # "Fort Wayne, IN": Indiana, not India. The town is listed in the US gazetteer under IN.
    country, _, s = ctry(run, ["12 Elm St", "Fort Wayne, IN"])
    assert country != "IN"


def test_street_name_that_ends_in_a_country_name_is_not_a_country(run):
    country, _, s = ctry(run, ["175 Rue Anatole France", "21000 Dijon"])
    assert "country" not in s.roles.values()


def test_northern_ireland_is_not_ireland(run):
    assert ctry(run, ["BELFAST BT2 2RY, 164 CLARK CRESCENT, NORTHERN IRELAND"])[0] == "GB"


def test_conflicting_evidence_is_flagged(run):
    country, _, s = ctry(run, ["12 Main St", "Bristol BS6 7QD", "Ireland"])
    assert "country_conflict" in s.flags


def test_a_hint_that_disagrees_with_explicit_text_is_a_conflict(run):
    _, _, s = ctry(run, ["12 Main St", "Cork T12 AC34", "IE"], hint="GB")
    assert s.country == "IE" and "hint_conflict" in s.flags


def test_agreeing_hint_raises_confidence(run):
    _, _, a = ctry(run, ["10 Elm Way", "Bristol BS6 7QD"])
    _, _, b = ctry(run, ["10 Elm Way", "Bristol BS6 7QD"], hint="GB")
    assert b.confidence["Ctry"] > a.confidence["Ctry"]


def test_country_tokens_are_consumed_and_ctry_is_the_iso_code(run):
    _, _, s = ctry(run, ["5 Rue X", "75008 Paris", "France"])
    assert s.fields["Ctry"] == "FR" and s.text[slice(*s.spans["Ctry"][0])] == "France"


# -- postcode --------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("lines,expected", [
    (["Cork T12 AC34", "IE"], "T12 AC34"),
    (["Cork T12AC34", "IE"], "T12AC34"),
    (["York YO10 5LB", "GB"], "YO10 5LB"),
    (["York YO10", "5LB", "GB"], "YO10 5LB"),
    (["Haarlem 2011VK", "NL"], "2011VK"),
    (["3011 TL", "Rotterdam", "NL"], "3011 TL"),
    (["Rotterdam 3011", "TL", "NL"], "3011 TL"),
    (["Atlanta, GA 30317-2153", "US"], "30317-2153"),
    (["Halifax NS B3H2R6", "CA"], "B3H2R6"),
    (["Pune, Maharashtra 411 001", "India"], "411 001"),
    (["75008 Paris", "France"], "75008"),
])
def test_postcode_forms(run, lines, expected):
    s = run(lines, "country postcode")
    assert s.fields.get("PstCd") == expected


def test_a_five_digit_house_number_is_not_the_zip(run):
    s = run(["12345 Main St", "Austin, TX 78701", "US"], "country postcode")
    assert s.fields["PstCd"] == "78701"


def test_postcode_split_over_a_comma_and_a_line_break(run):
    s = run(["Victoria, BC V8W,", "7K9 CA"], "country postcode")
    assert s.fields["PstCd"] == "V8W 7K9"


def test_a_partial_postcode_is_kept_and_flagged(run):
    s = run(["Unit 5, Fenway Park", "D24"], "country postcode", hint="IE")
    assert s.fields["PstCd"] == "D24" and "partial_postcode" in s.flags and s.confidence["PstCd"] < 0.8


def test_no_postcode_leaves_the_field_unset(run):
    assert "PstCd" not in run(["12 Main St", "Cork", "IE"], "country postcode").fields


def test_postcode_span_points_into_the_text(run):
    s = run(["Cork T12 AC34", "IE"], "country postcode")
    assert s.text[slice(*s.spans["PstCd"][0])] == "T12 AC34"


# -- region ----------------------------------------------------------------------------------------------------------
def test_irish_county_keeps_its_prefix(run):
    assert run(["Kinvara", "Co. Galway H91 W3R7", "IE"], "country postcode region").fields["CtrySubDvsn"] == "Co. Galway"
    assert run(["Kinvara", "County Galway", "IE"], "country postcode region").fields["CtrySubDvsn"] == "County Galway"


def test_bare_irish_county_name_is_not_a_region(run):
    assert "CtrySubDvsn" not in run(["Kinvara", "Galway H91 W3R7", "IE"], "country postcode region").fields


def test_us_state_by_abbreviation_and_by_name(run):
    assert run(["Atlanta, GA 30317", "US"], "country postcode region").fields["CtrySubDvsn"] == "GA"
    assert run(["Seattle, Washington 98129", "US"], "country postcode region").fields["CtrySubDvsn"] == "Washington"


def test_state_name_inside_a_street_name_is_not_a_region(run):
    s = run(["331 Washington Street", "Atlanta, GA 30317", "US"], "country postcode region")
    assert s.fields["CtrySubDvsn"] == "GA"


def test_canadian_province_written_after_the_postcode(run):
    assert run(["Gosforth NE3 8RA North Yorkshire", "GB"], "country postcode region").fields["CtrySubDvsn"] == "North Yorkshire"
    assert run(["H3A 0P8 Québec Montréal", "CA"], "country postcode region").fields["CtrySubDvsn"] == "Québec"


def test_a_region_that_is_also_a_town_needs_another_town(run):
    only = run(["Delhi 110092", "India"], "country postcode region")
    assert "CtrySubDvsn" not in only.fields
    both = run(["New Delhi Delhi 110005", "India"], "country postcode region")
    assert both.fields["CtrySubDvsn"] == "Delhi"


def test_region_is_never_written_for_france_germany_netherlands(run):
    assert "CtrySubDvsn" not in run(["10115 Berlin", "Deutschland"], "country postcode region").fields
