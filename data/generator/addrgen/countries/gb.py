"""United Kingdom: complex postcodes, flats and building names (labelling guide sections 2, 3, 6)."""
from __future__ import annotations

import random

from addrgen.countries.base import CountryModule, register
from addrgen.model import Part, TownBlock

# (post town, outward codes, county or None, constituent country, localities). A locality is written only next to
# the post town it belongs to.
POST_TOWNS = (
    ("Bristol", ("BS1", "BS2", "BS3", "BS6", "BS8"), None, "England", ("Clifton", "Redland", "Bedminster", "Southville", "Henleaze")),
    ("Bath", ("BA1", "BA2"), "Somerset", "England", ("Widcombe", "Combe Down", "Weston", "Larkhall")),
    ("Canterbury", ("CT1", "CT2"), "Kent", "England", ("Wincheap", "Sturry")),
    ("Oxford", ("OX1", "OX2", "OX4"), "Oxfordshire", "England", ("Headington", "Jericho", "Summertown", "Cowley")),
    ("Cambridge", ("CB1", "CB2", "CB4"), "Cambridgeshire", "England", ("Chesterton", "Trumpington", "Cherry Hinton", "Newnham")),
    ("Leeds", ("LS1", "LS2", "LS6"), "West Yorkshire", "England", ("Headingley", "Chapel Allerton", "Armley", "Roundhay")),
    ("Manchester", ("M1", "M2", "M4", "M13"), "Greater Manchester", "England", ("Didsbury", "Chorlton", "Ancoats", "Withington")),
    ("Birmingham", ("B1", "B2", "B15"), "West Midlands", "England", ("Edgbaston", "Moseley", "Selly Oak", "Harborne")),
    ("London", ("SW1A", "EC1A", "N1", "E14", "W1K", "SE1", "NW1", "WC2N"), None, "England",
     ("Islington", "Brixton", "Hackney", "Kensington", "Whitechapel", "Camden Town")),
    ("Norwich", ("NR1", "NR2"), "Norfolk", "England", ("Thorpe Hamlet", "Eaton", "Lakenham")),
    ("York", ("YO1", "YO10"), "North Yorkshire", "England", ("Heworth", "Acomb", "Fulford")),
    ("Exeter", ("EX1", "EX4"), "Devon", "England", ("Heavitree", "St Thomas", "Pennsylvania")),
    ("Reading", ("RG1", "RG30"), "Berkshire", "England", ("Caversham", "Tilehurst", "Whitley")),
    ("Brighton", ("BN1", "BN2"), "East Sussex", "England", ("Kemptown", "Preston Park", "Hanover")),
    ("Newcastle upon Tyne", ("NE1", "NE2"), "Tyne and Wear", "England", ("Jesmond", "Gosforth", "Heaton")),
    ("Cardiff", ("CF10", "CF11", "CF24"), None, "Wales", ("Roath", "Cathays", "Llandaff", "Canton")),
    ("Swansea", ("SA1", "SA2"), None, "Wales", ("Sketty", "Uplands", "Mumbles")),
    ("Edinburgh", ("EH1", "EH2", "EH3"), None, "Scotland", ("Leith", "Morningside", "Stockbridge")),
    ("Glasgow", ("G1", "G2", "G12"), None, "Scotland", ("Partick", "Govanhill", "Hillhead")),
    ("Aberdeen", ("AB10", "AB11"), None, "Scotland", ("Torry", "Cults")),
    ("Belfast", ("BT1", "BT2", "BT7"), None, "Northern Ireland", ("Stranmillis", "Malone")),
)

# Every locality that may be written beside a post town, by lower-cased town: used by the tests.
LOCALITIES_BY_TOWN = {t.casefold(): frozenset(x.casefold() for x in locs) for t, _, _, _, locs in POST_TOWNS}

# The inward half of a UK postcode: a digit, then two letters that exclude C, I, K, M, O and V.
_INWARD_LETTERS = "ABDEFGHJLNPQRSTUWXYZ"


@register
class UnitedKingdom(CountryModule):
    code = "GB"
    locale = "en_GB"
    country_names = ("United Kingdom", "UK", "Great Britain")
    street_bases = ("High", "Church", "Station", "Park", "Victoria", "Albert", "Mill", "Chapel", "Queen", "King",
                    "Green", "Manor", "Windsor", "York", "Orchard")
    street_suffixes = (("Street", 0.30), ("Road", 0.30), ("Lane", 0.10), ("Avenue", 0.08), ("Drive", 0.06),
                       ("Close", 0.08), ("Terrace", 0.02), ("Way", 0.03), ("Gardens", 0.02), ("Crescent", 0.02),
                       ("Place", 0.02), ("Grove", 0.02))
    building_bases = ("Marlow", "Riverside", "Kingsway", "Albion", "Regent", "Windsor", "Hawthorn", "Beech",
                      "Elmwood", "Oakfield", "Rosebery", "Highfield")
    building_words = (("House", 0.28), ("Court", 0.25), ("Lodge", 0.08), ("Tower", 0.05), ("Building", 0.06),
                      ("Centre", 0.04), ("Plaza", 0.02), ("Mansions", 0.07), ("Cottage", 0.15))
    place_names = ("Riverside", "Meridian", "Northgate", "Eastpoint", "Greenhills", "Westpark", "Lakeside", "Harbour")
    template_weights = {
        "number_street": 6, "street_only": 0.5, "house_name_street": 2, "building_street_number": 1.5,
        "flat_number_street": 3, "flat_in_building": 3, "floor_number_street": 1, "unit_business_park": 1,
        "po_box": 0.7, "rural_house": 0.7, "locality_number_street": 1.5,
    }

    def town_block(self, rng: random.Random, difficulty: str, want_locality: bool) -> TownBlock:
        town, outwards, county, constituent, suburbs = rng.choice(POST_TOWNS)
        postcode = f"{rng.choice(outwards)} {rng.randint(1, 9)}{rng.choice(_INWARD_LETTERS)}{rng.choice(_INWARD_LETTERS)}"
        # UK post towns are conventionally written in capitals; that is a natural variation, not a corruption.
        town_text = town.upper() if rng.random() < 0.4 else town

        segments: list[list[Part]] = []
        if want_locality or rng.random() < 0.2:
            segments.append([Part("TwnLctnNm", rng.choice(suburbs))])
        if rng.random() < 0.25:  # postcode on its own line is standard UK practice
            segments.append([Part("TwnNm", town_text)])
            segments.append([Part("PstCd", postcode)])
        else:
            segments.append([Part("TwnNm", town_text), Part("PstCd", postcode)])
        if county and rng.random() < 0.3:
            segments.append([Part("CtrySubDvsn", county)])
        elif rng.random() < 0.2:
            segments.append([Part("CtrySubDvsn", constituent)])
        return TownBlock(segments, set())

    def split_postcode(self, postcode: str) -> tuple[str, str] | None:
        parts = postcode.split(" ")
        return (parts[0], parts[1]) if len(parts) == 2 else None
