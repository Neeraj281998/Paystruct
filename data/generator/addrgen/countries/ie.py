"""Ireland: Eircodes, many addresses without street numbers, Dublin postal districts (labelling guide sections 1, 4, 5)."""
from __future__ import annotations

import random

from addrgen.countries.base import CountryModule, register
from addrgen.model import Part, TownBlock

# Eircode unique identifiers use these 25 characters.
_EIRCODE_CHARS = "0123456789ACDEFHKNPRTVWXY"

# (town, county, routing key)
TOWNS = (
    ("Cork", "Cork", "T12"), ("Galway", "Galway", "H91"), ("Limerick", "Limerick", "V94"),
    ("Waterford", "Waterford", "X91"), ("Kilkenny", "Kilkenny", "R95"), ("Sligo", "Sligo", "F91"),
    ("Athlone", "Westmeath", "N37"), ("Drogheda", "Louth", "A92"), ("Dundalk", "Louth", "A91"),
    ("Letterkenny", "Donegal", "F92"), ("Tralee", "Kerry", "V92"), ("Ennis", "Clare", "V95"),
    ("Wexford", "Wexford", "Y35"), ("Navan", "Meath", "C15"), ("Carlow", "Carlow", "R93"),
    ("Naas", "Kildare", "W91"), ("Killarney", "Kerry", "V93"), ("Mullingar", "Westmeath", "N91"),
    ("Cavan", "Cavan", "H12"), ("Castlebar", "Mayo", "F23"), ("Dún Laoghaire", "Dublin", "A96"),
    ("Bray", "Wicklow", "A98"), ("Swords", "Dublin", "K67"), ("Tullamore", "Offaly", "R35"),
)

# Dublin postal districts: (written town, routing key). There is no Dublin 19, 21 or 23.
DUBLIN_DISTRICTS = tuple(
    (f"Dublin {n}", f"D{n:02d}") for n in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 22, 24)
) + (("Dublin 6W", "D6W"),)

# Suburbs that can sit on a line before the district.
DUBLIN_LOCALITIES = {
    "Dublin 1": ("Docklands", "North Wall"), "Dublin 2": ("Portobello",), "Dublin 4": ("Ballsbridge", "Sandymount"),
    "Dublin 6": ("Ranelagh", "Rathmines", "Terenure"), "Dublin 7": ("Phibsborough", "Stoneybatter"),
    "Dublin 8": ("Kilmainham", "Rialto"), "Dublin 9": ("Drumcondra", "Santry"), "Dublin 12": ("Crumlin", "Walkinstown"),
    "Dublin 14": ("Dundrum", "Churchtown"), "Dublin 15": ("Blanchardstown", "Castleknock"),
    "Dublin 18": ("Sandyford", "Cabinteely"), "Dublin 24": ("Tallaght", "Kilnamanagh"),
}

LOCALITIES = (
    "Ballybrit", "Knocknacarra", "Mahon", "Douglas", "Salthill", "Oranmore", "Maynooth", "Glanmire", "Ballincollig",
    "Raheen", "Castletroy", "Shankill", "Kilcock", "Rathfarnham", "Clondalkin", "Lucan", "Carrigaline", "Blarney",
)


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
            suburbs = DUBLIN_LOCALITIES.get(town)
            locality = rng.choice(suburbs) if suburbs and (want_locality or rng.random() < 0.3) else None
            county = "Co. Dublin" if rng.random() < 0.10 else None
        else:
            town, county_name, key = rng.choice(TOWNS)
            locality = rng.choice(LOCALITIES) if want_locality or rng.random() < 0.25 else None
            county = None
            if rng.random() < 0.3:
                county = f"Co. {county_name}" if rng.random() < 0.5 else f"County {county_name}"

        if locality:
            segments.append([Part("TwnLctnNm", locality)])
        segments.append([Part("TwnNm", town), Part("PstCd", f"{key} {eircode_id}")])
        if county:
            segments.append([Part("CtrySubDvsn", county)])
        return TownBlock(segments, tags)

    def split_postcode(self, postcode: str) -> tuple[str, str] | None:
        parts = postcode.split(" ")
        return (parts[0], parts[1]) if len(parts) == 2 else None
