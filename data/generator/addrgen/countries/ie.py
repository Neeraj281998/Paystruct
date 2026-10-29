"""Ireland: Eircodes, many addresses without street numbers, Dublin postal districts (labelling guide sections 1, 4, 5)."""
from __future__ import annotations

import random

from addrgen.countries.base import CountryModule, register
from addrgen.model import Part, TownBlock

# Eircode unique identifiers use these 25 characters.
_EIRCODE_CHARS = "0123456789ACDEFHKNPRTVWXY"

# (town, county, routing key, localities). A locality is written only next to the town it belongs to; a town with an
# empty tuple never gets one, because no locality is listed for it.
TOWNS = (
    ("Cork", "Cork", "T12", ("Douglas", "Mahon", "Blackrock", "Ballincollig", "Glanmire", "Bishopstown", "Wilton", "Togher", "Montenotte")),
    ("Galway", "Galway", "H91", ("Salthill", "Knocknacarra", "Renmore", "Oranmore", "Claregalway", "Ballybrit", "Mervue", "Doughiska")),
    ("Limerick", "Limerick", "V94", ("Castletroy", "Raheen", "Dooradoyle", "Annacotty", "Caherdavin", "Corbally")),
    ("Waterford", "Waterford", "X91", ("Tramore", "Ferrybank", "Ballybeg", "Lisduggan")),
    ("Kilkenny", "Kilkenny", "R95", ()),
    ("Sligo", "Sligo", "F91", ("Strandhill", "Rosses Point")),
    ("Athlone", "Westmeath", "N37", ("Monksland", "Coosan")),
    ("Drogheda", "Louth", "A92", ("Mornington", "Termonfeckin")),
    ("Dundalk", "Louth", "A91", ("Blackrock", "Castletown", "Haggardstown")),
    ("Letterkenny", "Donegal", "F92", ("Ballyraine",)),
    ("Tralee", "Kerry", "V92", ("Ballymullen", "Blennerville")),
    ("Ennis", "Clare", "V95", ()),
    ("Wexford", "Wexford", "Y35", ()),
    ("Navan", "Meath", "C15", ("Athlumney", "Kentstown")),
    ("Carlow", "Carlow", "R93", ("Graiguecullen",)),
    ("Naas", "Kildare", "W91", ("Sallins", "Johnstown")),
    ("Killarney", "Kerry", "V93", ("Muckross", "Fossa")),
    ("Mullingar", "Westmeath", "N91", ()),
    ("Cavan", "Cavan", "H12", ()),
    ("Castlebar", "Mayo", "F23", ()),
    ("D\u00fan Laoghaire", "Dublin", "A96", ("Glasthule", "Monkstown", "Sandycove")),
    ("Bray", "Wicklow", "A98", ("Ballywaltrim", "Little Bray")),
    ("Swords", "Dublin", "K67", ("Applewood", "Seatown")),
    ("Tullamore", "Offaly", "R35", ()),
)

# Dublin postal districts: (written town, routing key). There is no Dublin 19, 21 or 23.
DUBLIN_DISTRICTS = tuple(
    (f"Dublin {n}", f"D{n:02d}") for n in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 22, 24)
) + (("Dublin 6W", "D6W"),)

# Suburbs, each listed under the postal district it is in.
DUBLIN_LOCALITIES = {
    "Dublin 1": ("Docklands", "North Wall"), "Dublin 2": ("Grand Canal Dock",),
    "Dublin 3": ("Clontarf", "Fairview", "Marino"), "Dublin 4": ("Ballsbridge", "Sandymount", "Donnybrook"),
    "Dublin 5": ("Raheny", "Artane", "Donaghmede"), "Dublin 6": ("Ranelagh", "Rathmines", "Rathgar"),
    "Dublin 6W": ("Terenure", "Templeogue"), "Dublin 7": ("Phibsborough", "Stoneybatter"),
    "Dublin 8": ("Kilmainham", "Rialto", "Portobello"), "Dublin 9": ("Drumcondra", "Santry", "Glasnevin"),
    "Dublin 10": ("Ballyfermot",), "Dublin 11": ("Finglas", "Glasnevin"), "Dublin 12": ("Crumlin", "Walkinstown"),
    "Dublin 13": ("Sutton", "Baldoyle"), "Dublin 14": ("Dundrum", "Churchtown", "Rathfarnham"),
    "Dublin 15": ("Blanchardstown", "Castleknock"), "Dublin 16": ("Ballinteer", "Knocklyon"),
    "Dublin 17": ("Coolock",), "Dublin 18": ("Sandyford", "Cabinteely", "Foxrock"), "Dublin 20": ("Chapelizod",),
    "Dublin 22": ("Clondalkin",), "Dublin 24": ("Tallaght", "Kilnamanagh"),
}

# Every locality that may be written beside a town, by lower-cased town: used by the tests.
LOCALITIES_BY_TOWN = {t.casefold(): frozenset(x.casefold() for x in locs) for t, _, _, locs in TOWNS} | {
    d.casefold(): frozenset(x.casefold() for x in locs) for d, locs in DUBLIN_LOCALITIES.items()}


@register
class Ireland(CountryModule):
    code = "IE"
    locale = "en_IE"
    country_names = ("Ireland", "Eire", "Republic of Ireland")
    street_bases = ("Main", "Church", "Mill", "Castle", "Bridge", "Convent", "Abbey", "Chapel", "Market", "Harbour",
                    "Orchard", "Station", "School", "Strand", "Priory")
    street_suffixes = (("Street", 0.35), ("Road", 0.25), ("Avenue", 0.08), ("Lane", 0.08), ("Drive", 0.06),
                       ("Terrace", 0.05), ("Close", 0.04), ("Square", 0.03), ("Quay", 0.02), ("Crescent", 0.02),
                       ("Gardens", 0.02), ("Grove", 0.03), ("Row", 0.01), ("Hill", 0.01))
    building_bases = ("Riverside", "Meadow", "Harbour", "Orchard", "Castle", "Willow", "Oakwood", "Seaview",
                      "Hillcrest", "Rosewood", "Maple", "Glenview", "Parkview", "Elm")
    building_words = (("House", 0.35), ("Court", 0.20), ("Lodge", 0.10), ("Tower", 0.05), ("Building", 0.05),
                      ("Centre", 0.05), ("Plaza", 0.03), ("Mansions", 0.03), ("Cottage", 0.14))
    place_names = ("Docklands", "Riverside", "Harbour", "Northgate", "Eastpoint", "Greenhills", "Westpark", "Lakeside")
    postcode_pattern = r"([ACDEFHKNPRTVWXY][0-9]{2}|D6W) ?[0-9ACDEFHKNPRTVWXY]{4}"
    region_pattern = r"(co\.|county) [a-z]+"
    template_weights = {
        "number_street": 6, "street_only": 2, "house_name_street": 2, "building_street_number": 1,
        "flat_number_street": 1.5, "flat_in_building": 1, "floor_number_street": 0.5, "unit_business_park": 1.5,
        "po_box": 1, "rural_house": 2.5, "locality_number_street": 1.5,
    }

    def town_block(self, rng: random.Random, difficulty: str, want_locality: bool) -> TownBlock:
        tags: set[str] = set()
        segments: list[list[Part]] = []
        eircode_id = "".join(rng.choice(_EIRCODE_CHARS) for _ in range(4))

        if difficulty == "hard" and rng.random() < 0.4:
            town, key = rng.choice(DUBLIN_DISTRICTS)
            tags.add("postal_district")
            suburbs = DUBLIN_LOCALITIES[town]
            locality = rng.choice(suburbs) if want_locality or rng.random() < 0.3 else None
            county = "Co. Dublin" if rng.random() < 0.10 else None
        else:
            candidates = [t for t in TOWNS if t[3]] if want_locality else TOWNS  # a locality needs a town that has some
            town, county_name, key, suburbs = rng.choice(candidates)
            locality = rng.choice(suburbs) if suburbs and (want_locality or rng.random() < 0.25) else None
            county = None
            if rng.random() < 0.3:
                county = f"Co. {county_name}" if rng.random() < 0.5 else f"County {county_name}"

        if locality:
            segments.append([Part("TwnLctnNm", locality)])
        segments.append([Part("TwnNm", town), Part("PstCd", f"{key} {eircode_id}")])
        if county:
            segments.append([Part("CtrySubDvsn", county)])
        return TownBlock(segments, tags)

    def known_towns(self) -> frozenset[str]:
        return frozenset(t.casefold() for t, *_ in TOWNS) | frozenset(d.casefold() for d, _ in DUBLIN_DISTRICTS)

    def split_postcode(self, postcode: str) -> tuple[str, str] | None:
        parts = postcode.split(" ")
        return (parts[0], parts[1]) if len(parts) == 2 else None
