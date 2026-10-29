"""United States: states, ZIP and ZIP+4, directionals in the street name (guide section 17)."""
from __future__ import annotations

import random

from addrgen.countries.base import CountryModule, _pick, ordinal, register
from addrgen.model import Part, TownBlock

# (city, state code, state name, three-digit ZIP prefixes); the last two digits are random.
CITIES = (
    ("New York", "NY", "New York", ("100", "101", "102")), ("Los Angeles", "CA", "California", ("900", "901")),
    ("Chicago", "IL", "Illinois", ("606", "607")), ("Houston", "TX", "Texas", ("770", "772")),
    ("Phoenix", "AZ", "Arizona", ("850", "852")), ("Philadelphia", "PA", "Pennsylvania", ("191", "190")),
    ("San Antonio", "TX", "Texas", ("782", "781")), ("San Diego", "CA", "California", ("921", "920")),
    ("Dallas", "TX", "Texas", ("752", "753")), ("Austin", "TX", "Texas", ("787", "786")),
    ("Seattle", "WA", "Washington", ("981", "980")), ("Denver", "CO", "Colorado", ("802", "800")),
    ("Boston", "MA", "Massachusetts", ("021", "022")), ("Atlanta", "GA", "Georgia", ("303", "300")),
    ("Miami", "FL", "Florida", ("331", "330")), ("Minneapolis", "MN", "Minnesota", ("554", "553")),
    ("Portland", "OR", "Oregon", ("972", "970")), ("Nashville", "TN", "Tennessee", ("372", "370")),
    ("Detroit", "MI", "Michigan", ("482", "481")), ("Charlotte", "NC", "North Carolina", ("282", "281")),
)
_TYPES = (("Street", 0.40), ("Avenue", 0.15), ("Boulevard", 0.06), ("Drive", 0.10), ("Lane", 0.05), ("Road", 0.10),
          ("Court", 0.03), ("Way", 0.03), ("Place", 0.02), ("Parkway", 0.02), ("Circle", 0.02), ("Trail", 0.01),
          ("Highway", 0.01))
_BASES = ("Main", "Oak", "Maple", "Cedar", "Elm", "Washington", "Lake", "Hill", "Park", "Pine", "Sunset", "Church",
          "Jefferson", "Lincoln", "Madison", "Highland", "Ridge", "Willow")
_ABBREVIATIONS = {"Street": ("St",), "Avenue": ("Ave",), "Boulevard": ("Blvd",), "Drive": ("Dr",), "Lane": ("Ln",),
                  "Road": ("Rd",), "Court": ("Ct",), "Place": ("Pl",), "Parkway": ("Pkwy",), "Circle": ("Cir",),
                  "Trail": ("Trl",), "Highway": ("Hwy",)}
_STREET_WORDS = frozenset(w.casefold() for w in list(_ABBREVIATIONS) + [a for abbr in _ABBREVIATIONS.values() for a in abbr] + ["Way", "Terrace"])
_BUILDING_WORDS = (("Building", 0.35), ("Tower", 0.2), ("Plaza", 0.2), ("Center", 0.15), ("Complex", 0.1))
_DIRECTIONS = ("N", "S", "E", "W")
_POST_DIRECTIONS = ("NW", "NE", "SW", "SE")


@register
class UnitedStates(CountryModule):
    code = "US"
    locale = "en_US"
    country_names = ("USA", "U.S.A.", "United States", "United States of America")
    street_bases = _BASES
    street_suffixes = _TYPES
    building_bases = ("Lakeside", "Meridian", "Capitol", "Liberty", "Parkview", "Empire", "Riverside", "Summit")
    building_words = _BUILDING_WORDS
    template_weights = {
        "number_street": 7, "street_only": 0.2, "building_number_street": 1.5, "flat_number_street": 3,
        "flat_in_building": 1.5, "floor_number_street": 1.5, "po_box": 0.7,
    }

    room_after_street = True
    postcode_has_space = False
    can_drop_postcode_space = False
    street_abbreviations = _ABBREVIATIONS
    room_abbreviations = {"Apartment": ("Apt", "Apt."), "Suite": ("Ste",)}
    street_words = _STREET_WORDS
    building_word_set = frozenset(w.casefold() for w, _ in _BUILDING_WORDS)
    protected_words = _STREET_WORDS | building_word_set | {d.casefold() for d in _DIRECTIONS + _POST_DIRECTIONS}
    room_pattern = r"((Apartment|Apt\.?|Suite|Ste|Unit) \d+[A-C]?|#\d+[A-C]?)"
    floor_pattern = r"(\d+(st|nd|rd|th) Floor|Fl \d+)"
    po_box_pattern = r"(PO|P\.O\.) Box \d+"
    building_number_pattern = r"\d+"
    postcode_pattern = r"\d{5}(-\d{4})?"
    region_pattern = "|".join(sorted({c for _, c, _, _ in CITIES} | {n for _, _, n, _ in CITIES}))

    def street_name(self, rng, fake):
        if rng.random() < 0.15:  # "5th Street"
            name = f"{ordinal(rng.randint(1, 20))} {_pick(rng, _TYPES)}"
        else:
            base = self.surname(rng, fake) if rng.random() < 0.25 else rng.choice(_BASES)
            name = f"{base} {_pick(rng, _TYPES)}"
        if rng.random() < 0.25:
            return f"{rng.choice(_DIRECTIONS)} {name}"
        return f"{name} {rng.choice(_POST_DIRECTIONS)}" if rng.random() < 0.10 else name

    def building_name(self, rng, fake):
        return f"{rng.choice(self.building_bases)} {_pick(rng, _BUILDING_WORDS)}"

    def building_number(self, rng):
        return str(rng.randint(1, 999) if rng.random() < 0.6 else rng.randint(1000, 9999))

    def room(self, rng):
        keyword = _pick(rng, (("Apartment", 0.3), ("Suite", 0.3), ("Unit", 0.2), ("#", 0.2)))
        suffix = rng.choice("ABC") if rng.random() < 0.2 else ""
        if keyword == "#":
            return f"#{rng.randint(1, 60)}{suffix}"
        n = rng.randint(100, 999) if keyword == "Suite" else rng.randint(1, 60)
        return f"{keyword} {n}{suffix}"

    def floor(self, rng):
        n = rng.randint(1, 30)
        return f"{ordinal(n)} Floor" if rng.random() < 0.7 else f"Fl {n}"

    def po_box(self, rng):
        return f"PO Box {rng.randint(1, 99999)}" if rng.random() < 0.6 else f"P.O. Box {rng.randint(1, 99999)}"

    def is_street_name(self, text):
        return any(w.rstrip(".").casefold() in self.street_words for w in text.split(" "))

    def town_block(self, rng: random.Random, difficulty: str, want_locality: bool) -> TownBlock:
        city, code, name, prefixes = rng.choice(CITIES)
        zip_code = f"{rng.choice(prefixes)}{rng.randint(0, 99):02d}"
        if rng.random() < 0.2:
            zip_code += f"-{rng.randint(0, 9999):04d}"
        state = code if rng.random() < 0.6 else name
        return TownBlock([[Part("TwnNm", city, comma_after=True), Part("CtrySubDvsn", state), Part("PstCd", zip_code)]], set())

    def split_postcode(self, postcode):
        return None  # a ZIP has no natural place to break

    def known_towns(self):
        return frozenset(c[0].casefold() for c in CITIES)
