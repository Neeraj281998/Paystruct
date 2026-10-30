"""landmark, po box, floor, unit, town, street, locality: one test group per rule."""
import pytest

FULL = "country postcode region pobox floor unit town landmark street locality"


def fields(run, lines, rules=FULL, hint=None):
    return run(lines, rules, hint).fields


# -- po box, floor, unit ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("lines,field,value", [
    (["PO Box 1234", "Cork T12 AC34", "IE"], "PstBx", "PO Box 1234"),
    (["P.O. Box 8841", "Atlanta, GA 30317", "US"], "PstBx", "P.O. Box 8841"),
    (["Postfach 101112", "70049 Stuttgart", "Deutschland"], "PstBx", "Postfach 101112"),
    (["Postbus 8423", "3503 RK Utrecht", "NL"], "PstBx", "Postbus 8423"),
    (["BP 4021", "69256 LYON CEDEX 09", "France"], "PstBx", "BP 4021"),
    (["C.P. 4417", "Halifax NS B3H 2R6", "CA"], "PstBx", "C.P. 4417"),
])
def test_pobox(run, lines, field, value):
    assert fields(run, lines, "country postcode region pobox")[field] == value


@pytest.mark.parametrize("lines,value", [
    (["Ground Floor", "Cork T12 AC34", "IE"], "Ground Floor"),
    (["2nd Floor, 14 Elm Way", "Bristol BS6 7QD", "GB"], "2nd Floor"),
    (["3ème étage", "75008 Paris", "France"], "3ème étage"),
    (["Rez-de-chaussée", "75008 Paris", "France"], "Rez-de-chaussée"),
    (["Hauptstraße 5", "3. OG", "10115 Berlin", "Deutschland"], "3. OG"),
    (["Begane grond", "Kaleplein 198", "2621 KK Delft", "NL"], "Begane grond"),
    (["800 Tideway Dr, 5th Floor", "Seattle, WA 98101", "US"], "5th Floor"),
])
def test_floor(run, lines, value):
    assert fields(run, lines, "country postcode region pobox floor")["Flr"] == value


@pytest.mark.parametrize("lines,value", [
    (["Flat 3, 14 Elm Way", "Bristol BS6 7QD", "GB"], "Flat 3"),
    (["Flat A D16 E648", "64 Devilly Street", "Dublin 16", "IE"], "Flat A"),
    (["Unit 4, 3rd floor", "Wilgenlaan 17", "5611 JK Eindhoven", "NL"], "Unit 4"),
    (["Apt 5B, 450 Larkspur Ave", "Pasadena, CA 91101", "US"], "Apt 5B"),
    (["Suite 200", "450 Larkspur Ave", "Pasadena, CA 91101", "US"], "Suite 200"),
    (["Bureau 305", "1450 boul. Aimé-Dufresne", "Montréal QC H3B 2K4", "Canada"], "Bureau 305"),
    (["#204 - 1177 STANTON ST", "Victoria BC", "CA"], "#204"),
    (["Whg. 59", "Hübelstraße 159", "51143 Köln", "DE"], "Whg. 59"),
    (["Flat No. 301, Sunrise Residency", "Pune, Maharashtra 411001", "India"], "Flat No. 301"),
])
def test_unit_keeps_its_keyword(run, lines, value):
    assert fields(run, lines, "country postcode region pobox floor unit")["Room"] == value


def test_a_unit_keyword_without_an_identifier_is_not_a_unit(run):
    assert "Room" not in fields(run, ["Flat Road", "Cork T12 AC34", "IE"], "country postcode region pobox floor unit")


# -- landmark --------------------------------------------------------------------------------------------------------
def test_landmarks_are_not_labelled_and_are_reported(run):
    s = run(["Plot 22, Behind old water tank, Vaishali Nagar", "Jaipur, Rajasthan 302021", "India"], FULL)
    assert "Behind old water tank" not in " ".join(s.fields.values())
    assert [s.text_of([i for i, r in s.roles.items() if r == "landmark"])] == ["Behind old water tank"]


def test_landmark_phrase_stops_at_the_town(run):
    s = run(["No. 10 Hospital Marg opp. Railway Station Jaipur Rajasthan 302006", "India"], FULL)
    assert s.fields["TwnNm"] == "Jaipur" and s.fields["BldgNb"] == "No. 10" and s.fields["StrtNm"] == "Hospital Marg"


def test_landmarks_exist_only_for_countries_that_define_them(run):
    s = run(["12 Near Road", "Cork T12 AC34", "IE"], FULL)
    assert s.fields["StrtNm"] == "Near Road"


# -- town ------------------------------------------------------------------------------------------------------------
def test_town_written_before_and_after_the_postcode(run):
    assert fields(run, ["12 Main St", "Cork T12 AC34", "IE"])["TwnNm"] == "Cork"
    assert fields(run, ["5 Rue X", "75008 Paris", "France"])["TwnNm"] == "Paris"


def test_town_suffixes_stay_with_the_town(run):
    assert fields(run, ["64 Devilly Street", "Dublin 16", "D16 E648", "IE"])["TwnNm"] == "Dublin 16"
    assert fields(run, ["64 Devilly Street", "Dublin 6W", "D6W 5D75", "IE"])["TwnNm"] == "Dublin 6W"
    assert fields(run, ["12 rue Haute", "75013 Paris 13e", "FR"])["TwnNm"] == "Paris 13e"
    assert fields(run, ["APPARTEMENT 14, 174 RUE DE VERDUN, 29200 BREST CEDEX 17"], hint="FR")["TwnNm"] == "BREST CEDEX 17"


def test_no_town_written_leaves_twnnm_unset(run):
    s = run(["27 rue des Acacias-Fleuris", "69003", "France"], FULL)
    assert "TwnNm" not in s.fields and s.fields["PstCd"] == "69003"


def test_the_gazetteer_never_supplies_a_town(run):
    # D24 is a Dublin routing key and the country is Ireland, yet no town is written, so none is output.
    s = run(["Unit 5, Fenway Business Park", "D24", "IE"], FULL)
    assert "TwnNm" not in s.fields


def test_a_street_named_after_a_town_is_not_the_town(run):
    s = run(["4 Dublin Road", "Cork T12 AC34", "IE"], FULL)
    assert s.fields["TwnNm"] == "Cork" and s.fields["StrtNm"] == "Dublin Road"


def test_a_street_word_that_is_also_a_town_is_not_the_town(run):
    s = run(["122 Khan Street", "LONDON", "EC1A 3GT, United Kingdom"], FULL)
    assert s.fields["TwnNm"] == "LONDON" and s.fields["StrtNm"] == "Khan Street"


def test_town_inside_a_street_phrase_is_skipped(run):
    s = run(["96 Rue de la Paix, 57000 Metz, FR"], FULL)
    assert s.fields["TwnNm"] == "Metz" and s.fields["StrtNm"] == "Rue de la Paix"


def test_a_written_town_the_gazetteer_lacks_is_kept_with_low_confidence(run):
    s = run(["12 Main St", "Ballyvaughan", "H91 W3R7", "IE"], FULL)
    assert s.fields["TwnNm"] == "Ballyvaughan" and s.confidence["TwnNm"] <= 0.5 and "town_unverified" in s.flags


def test_us_town_whose_state_disagrees_is_flagged(run):
    s = run(["12 Main St", "Atlanta, TX 30317", "US"], FULL)
    assert "region_town_mismatch" in s.flags


def test_a_same_name_town_in_another_state_is_not_a_mismatch(run):
    s = run(["12 Main St", "Dublin, CA 94568", "US"], FULL)
    assert "region_town_mismatch" not in s.flags


def test_town_nearest_the_postcode_wins(run):
    s = run(["Plot 146, Link Road, Juhu, Mumbai, Maharashtra 400049", "India"], FULL)
    assert s.fields["TwnNm"] == "Mumbai" and s.fields["TwnLctnNm"] == "Juhu"


# -- street, number, building ----------------------------------------------------------------------------------------
@pytest.mark.parametrize("lines,expect", [
    (["64B MARKET SQUARE", "KILKENNY R95 NRE2", "IE"], {"BldgNb": "64B", "StrtNm": "MARKET SQUARE"}),
    (["Flat 2, 14 Marlow Court", "Bristol BS6 7QD", "GB"], {"Room": "Flat 2", "BldgNb": "14", "BldgNm": "Marlow Court"}),
    (["Rose Cottage, High Street", "Bristol BS6 7QD", "GB"], {"BldgNm": "Rose Cottage", "StrtNm": "High Street"}),
    (["Hamilton Lodge Victoria Ave. Bristol BS6 7QD GB"], {"BldgNm": "Hamilton Lodge", "StrtNm": "Victoria Ave."}),
    (["Unit 4 Block B Docklands Business Park", "Cork T12 AC34", "IE"], {"Room": "Unit 4", "BldgNm": "Block B Docklands Business Park"}),
    (["Rathmines Road Lower", "Dublin 6", "D06 N4R2", "IE"], {"StrtNm": "Rathmines Road Lower"}),
    (["32 BIS RUE DU CHÂTEAU", "13016 MARSEILLE 16E, FR"], {"BldgNb": "32 BIS", "StrtNm": "RUE DU CHÂTEAU"}),
    (["Résidence Le Clos,", "175 Rue Anatole France,", "21000 Dijon", "FR"], {"BldgNm": "Résidence Le Clos", "BldgNb": "175", "StrtNm": "Rue Anatole France"}),
    (["Résidence Le Central  Rue du Château  29200 Brest France"], {"BldgNm": "Résidence Le Central", "StrtNm": "Rue du Château"}),
    (["Hübelstraße  159-161", "51143 Köln DE"], {"StrtNm": "Hübelstraße", "BldgNb": "159-161"}),
    (["Gartestr. 95", "Münster 48079", "DE"], {"StrtNm": "Gartestr.", "BldgNb": "95"}),
    (["Van Vastenhouwstraat 60", "3525 EA Utrecht", "NL"], {"StrtNm": "Van Vastenhouwstraat", "BldgNb": "60"}),
    (["5638 CD Eindhoven Gebouw West Pluijmplein 131 Unit 1 Nederland"], {"BldgNm": "Gebouw West", "StrtNm": "Pluijmplein", "BldgNb": "131"}),
    (["237 RUE DE LA MONTAGNE O SUITE 185 MONTRÉAL QC H3B 5R1 CA"], {"BldgNb": "237", "StrtNm": "RUE DE LA MONTAGNE O", "Room": "SUITE 185"}),
    (["21 Park Street W", "Victoria BC V8V 0C8, CA"], {"StrtNm": "Park Street W", "BldgNb": "21"}),
    (["826 E Oak Lane, Apartment 14, Austin, TX 78704, US"], {"StrtNm": "E Oak Lane", "BldgNb": "826", "Room": "Apartment 14"}),
    (["House No. 51  Link Road", "Vastrapur", "Pune Maharashtra 411001", "India"], {"BldgNb": "House No. 51", "StrtNm": "Link Road"}),
    (["Orchid Residency,", "No. 120, Mill Road,", "Pune, Maharashtra 411001, IN"], {"BldgNm": "Orchid Residency", "BldgNb": "No. 120", "StrtNm": "Mill Road"}),
    (["Lakeside Building,", "7802 Cear Street,", "Seattle, Washington 98129,", "U.S.A."], {"BldgNm": "Lakeside Building", "BldgNb": "7802", "StrtNm": "Cear Street"}),
])
def test_street_number_and_building(run, lines, expect):
    f = fields(run, lines, hint=None)
    for k, v in expect.items():
        assert f.get(k) == v, (k, f)


def test_street_with_no_number(run):
    f = fields(run, ["Rue Jean Jaurès,", "Paris 13e,", "FR,", "75013"])
    assert f["StrtNm"] == "Rue Jean Jaurès" and "BldgNb" not in f and f["TwnNm"] == "Paris 13e"


def test_ca_unit_prefix_is_split(run):
    f = fields(run, ["5-123 Kestrel Drive", "Kingston ON K7L 4V1"], hint="CA")
    assert f["Room"] == "5" and f["BldgNb"] == "123"


# -- locality --------------------------------------------------------------------------------------------------------
def test_locality_is_the_clean_segment_next_to_the_town(run):
    f = fields(run, ["139 Mill Street, Ballywaltrim, Bray A98 DTNF, IE"])
    assert f.get("TwnLctnNm") == "Ballywaltrim" and f["TwnNm"] == "Bray"


def test_indian_sector_is_a_locality(run):
    f = fields(run, ["Plot 80, Tilka Lane", "Sector 40", "Pune, Maharashtra 411001", "IN"])
    assert f["TwnLctnNm"] == "Sector 40"


def test_countries_without_localities_leave_the_segment_as_a_leftover(run):
    s = run(["12 rue Haute", "Quartier Nord", "75008 Paris", "France"], FULL)
    assert "TwnLctnNm" not in s.fields and s.free_indexes()
