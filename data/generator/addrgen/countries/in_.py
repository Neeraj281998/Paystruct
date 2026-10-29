"""India: long addresses, localities, six-digit PIN codes, unlabelled landmarks (guide section 18)."""
from __future__ import annotations

import random
import re

from addrgen.countries.base import CountryModule, _pick, ordinal, register
from addrgen.model import Part, TownBlock

# (city, state, first three digits of its PIN codes, localities). A locality is written only next to its own city.
# "{n}" in a locality is a sector number, for planned cities.
CITIES = (
    ("Pune", "Maharashtra", "411", ("Koregaon Park", "Kothrud", "Viman Nagar", "Hinjewadi", "Baner", "Aundh")),
    ("Mumbai", "Maharashtra", "400", ("Andheri East", "Bandra West", "Powai", "Juhu", "Dadar", "Borivali West")),
    ("Bengaluru", "Karnataka", "560", ("Koramangala", "Indiranagar", "Whitefield", "HSR Layout", "Jayanagar")),
    ("Chennai", "Tamil Nadu", "600", ("T. Nagar", "Adyar", "Anna Nagar", "Velachery")),
    ("New Delhi", "Delhi", "110", ("Connaught Place", "Saket", "Dwarka", "Karol Bagh", "Lajpat Nagar")),
    ("Hyderabad", "Telangana", "500", ("Banjara Hills", "Jubilee Hills", "Madhapur", "Gachibowli")),
    ("Kolkata", "West Bengal", "700", ("Salt Lake", "Ballygunge", "Behala", "New Town")),
    ("Ahmedabad", "Gujarat", "380", ("Navrangpura", "Satellite", "Maninagar", "Vastrapur")),
    ("Jaipur", "Rajasthan", "302", ("Malviya Nagar", "C-Scheme", "Vaishali Nagar", "Mansarovar")),
    ("Lucknow", "Uttar Pradesh", "226", ("Gomti Nagar", "Hazratganj", "Aliganj")),
    ("Noida", "Uttar Pradesh", "201", ("Sector {n}",)),
    ("Gurugram", "Haryana", "122", ("Sector {n}", "Sushant Lok")),
    ("Chandigarh", "Chandigarh", "160", ("Sector {n}",)),
)
_SECTOR = re.compile(r"Sector \d+")

_BASES = ("MG", "Station", "Link", "Ring", "Main", "Residency", "Church", "Temple", "Mill", "Market", "Nehru", "Gandhi",
          "Tilak", "Airport", "Hospital")
_TYPES = (("Road", 0.65), ("Marg", 0.10), ("Street", 0.10), ("Lane", 0.08), ("Cross", 0.07))
_BUILDING_WORDS = (("Residency", 0.25), ("Towers", 0.2), ("Heights", 0.15), ("Apartments", 0.15), ("Plaza", 0.1),
                   ("Complex", 0.1), ("Mansion", 0.05))
_BUILDING_NAMES = ("Sunrise", "Prestige", "Green", "Lotus", "Maple", "Shanti", "Royal", "Silver", "Golden", "Orchid")
_LANDMARKS = ("near City Mall", "opp. Railway Station", "behind SBI Bank", "next to Axis Bank ATM", "near Hanuman Temple",
              "opposite Central Park", "near Metro Station", "behind Bus Stand")
_STREET_WORDS = frozenset({"road", "rd", "marg", "street", "lane", "cross", "highway"})
_BUILDING_WORD_SET = frozenset(w.casefold() for w, _ in _BUILDING_WORDS)


@register
class India(CountryModule):
    code = "IN"
    locale = "en_IN"
    country_names = ("India",)
    street_bases = _BASES
    street_suffixes = _TYPES
    building_bases = _BUILDING_NAMES
    building_words = _BUILDING_WORDS
    template_weights = {
        "number_street": 5, "street_only": 0.3, "house_name_street": 1, "building_number_street": 2,
        "flat_number_street": 2, "flat_in_building": 3, "floor_number_street": 1.5, "rural_house": 1.5,
        "locality_number_street": 3,
    }

    postcode_has_space = None  # "411001" and "411 001" are both written
    can_drop_postcode_space = False
    street_abbreviations = {"Road": ("Rd",)}
    room_abbreviations = {}
    street_words = _STREET_WORDS
    building_word_set = _BUILDING_WORD_SET
    protected_words = _STREET_WORDS | _BUILDING_WORD_SET | {"marg"}
    room_pattern = r"Flat( No\.)? \d+"
    floor_pattern = r"\d+(st|nd|rd|th) Floor"
    po_box_pattern = r"(?!)"  # India has no PO box template here
    building_number_pattern = r"(Plot \d+|House No\. \d+|Door No\. \d+-\d-\d+|No\. \d+)"
    postcode_pattern = r"\d{3} ?\d{3}"
    region_pattern = "|".join(sorted({s for _, s, _, _ in CITIES}))

    def street_name(self, rng, fake):
        street_type = _pick(rng, _TYPES)
        if street_type == "Cross":
            return f"{ordinal(rng.randint(1, 20))} Cross"
        return f"{rng.choice(_BASES)} {street_type}"

    def building_name(self, rng, fake):
        return f"{rng.choice(_BUILDING_NAMES)} {_pick(rng, _BUILDING_WORDS)}"

    def building_number(self, rng):
        """The keyword stays in the value (guide section 18)."""
        roll = rng.random()
        if roll < 0.40:
            return f"Plot {rng.randint(1, 199)}"
        if roll < 0.70:
            return f"House No. {rng.randint(1, 199)}"
        if roll < 0.85:
            return f"Door No. {rng.randint(1, 99)}-{rng.randint(1, 9)}-{rng.randint(1, 99)}"
        return f"No. {rng.randint(1, 199)}"

    def room(self, rng):
        n = rng.randint(101, 1204)
        return f"Flat {n}" if rng.random() < 0.7 else f"Flat No. {n}"

    def floor(self, rng):
        return f"{ordinal(rng.randint(1, 12))} Floor"

    def street_parts(self, rng, fake, with_number=True):
        parts = super().street_parts(rng, fake, with_number)
        if with_number:
            parts[0].comma_after = True  # "Plot 12, MG Road"
        return parts

    def is_street_name(self, text):
        return text.split(" ")[-1].rstrip(".").casefold() in _STREET_WORDS

    def town_block(self, rng: random.Random, difficulty: str, want_locality: bool) -> TownBlock:
        town, state, prefix, localities = rng.choice(CITIES)
        pin = f"{prefix}{rng.randint(1, 99):03d}"
        if rng.random() < 0.2:
            pin = f"{pin[:3]} {pin[3:]}"  # also written with a space
        segments: list[list[Part]] = []
        if want_locality or rng.random() < 0.85:
            locality = rng.choice(localities).replace("{n}", str(rng.randint(1, 120)))
            segments.append([Part("TwnLctnNm", locality)])
        segments.append([Part("TwnNm", town, comma_after=True), Part("CtrySubDvsn", state), Part("PstCd", pin)])
        return TownBlock(segments, set())

    def make_truth(self, rng, difficulty):
        """Hard addresses may carry a landmark: text with no gold field, written between the street and the locality."""
        truth = super().make_truth(rng, difficulty)
        if difficulty == "hard" and rng.random() < 0.4:
            at = next(i for i, seg in enumerate(truth.segments) if any(p.field in ("TwnLctnNm", "TwnNm") for p in seg))
            truth.segments.insert(at, [Part(None, rng.choice(_LANDMARKS))])
            truth.tags.add("landmark")
        return truth

    def split_postcode(self, postcode):
        parts = postcode.split(" ")
        return (parts[0], parts[1]) if len(parts) == 2 else None

    def known_towns(self):
        return frozenset(c[0].casefold() for c in CITIES)


LOCALITIES_BY_TOWN = {c[0].casefold(): frozenset(x.casefold() for x in c[3] if "{n}" not in x) for c in CITIES}
SECTOR_TOWNS = frozenset(c[0].casefold() for c in CITIES if any("{n}" in x for x in c[3]))
