"""Canada: provinces, A1A 1A1 postcodes, English and French addresses (guide section 16)."""
from __future__ import annotations

import random

from addrgen.countries.base import CountryModule, _pick, ordinal, register
from addrgen.model import Part, TownBlock

# (town, province code, province name, first three characters of its postcodes, French-speaking)
TOWNS = (
    ("Toronto", "ON", "Ontario", ("M5V", "M4W", "M5H", "M6G", "M4Y"), False),
    ("Ottawa", "ON", "Ontario", ("K1P", "K1N", "K2P"), False), ("Hamilton", "ON", "Ontario", ("L8P", "L8N"), False),
    ("London", "ON", "Ontario", ("N6A", "N6B"), False), ("Mississauga", "ON", "Ontario", ("L5B", "L5M"), False),
    ("Montréal", "QC", "Québec", ("H3B", "H2X", "H4A", "H3A"), True),
    ("Québec", "QC", "Québec", ("G1R", "G1K", "G1V"), True),
    ("Vancouver", "BC", "British Columbia", ("V6B", "V6Z", "V5K", "V6E"), False),
    ("Victoria", "BC", "British Columbia", ("V8W", "V8V"), False),
    ("Calgary", "AB", "Alberta", ("T2P", "T3A", "T2R"), False), ("Edmonton", "AB", "Alberta", ("T5J", "T6E", "T5K"), False),
    ("Winnipeg", "MB", "Manitoba", ("R3C", "R3B"), False), ("Saskatoon", "SK", "Saskatchewan", ("S7K", "S7N"), False),
    ("Regina", "SK", "Saskatchewan", ("S4P", "S4S"), False), ("Halifax", "NS", "Nova Scotia", ("B3J", "B3H"), False),
    ("Fredericton", "NB", "New Brunswick", ("E3B", "E3A"), False),
    ("St. John's", "NL", "Newfoundland and Labrador", ("A1C", "A1B"), False),
    ("Charlottetown", "PE", "Prince Edward Island", ("C1A", "C1E"), False),
)
_LDU_LETTERS = "ABCEGHJKLMNPRSTVWXYZ"  # D, F, I, O, Q and U never appear

_EN_TYPES = (("Street", 0.40), ("Avenue", 0.20), ("Road", 0.12), ("Drive", 0.08), ("Crescent", 0.05), ("Boulevard", 0.05),
             ("Court", 0.04), ("Way", 0.03), ("Lane", 0.02), ("Trail", 0.01))
_EN_BASES = ("Main", "King", "Queen", "Yonge", "Bloor", "Dundas", "Front", "Elm", "Maple", "Oak", "Victoria", "Wellington",
             "Albert", "Church", "Park", "Lakeshore", "Bay")
_FR_TYPES = (("rue", 0.55), ("avenue", 0.15), ("boulevard", 0.12), ("chemin", 0.08), ("place", 0.05), ("côte", 0.03),
             ("montée", 0.02))
_FR_BASES = ("Sainte-Catherine", "Saint-Denis", "René-Lévesque", "du Parc", "de la Montagne", "Notre-Dame",
             "Saint-Laurent", "des Érables", "Sherbrooke", "de Bleury")
_EN_DIRECTIONS = ("West", "East", "W", "E")
_FR_DIRECTIONS = ("Ouest", "Est", "O")
_NAMES = ("Royal", "Harbour", "Lakeview", "Capital", "Maple", "Dominion")
_EN_BUILDING_WORDS = (("Building", 0.35), ("Tower", 0.2), ("Centre", 0.2), ("Plaza", 0.15), ("Complex", 0.1))
_FR_BUILDING_WORDS = (("Édifice", 0.45), ("Tour", 0.3), ("Complexe", 0.25))
_STREET_WORDS = frozenset({w for w, _ in _EN_TYPES} | {w for w, _ in _FR_TYPES} | {"Blvd", "St", "Ave", "Rd", "Dr", "Ln",
                                                                                    "Cres", "Ct", "Pl"})
_BUILDING_WORDS = frozenset(w.casefold() for w, _ in _EN_BUILDING_WORDS + _FR_BUILDING_WORDS)


@register
class Canada(CountryModule):
    code = "CA"
    locale = "en_CA"
    country_names = ("Canada",)
    street_bases = _EN_BASES
    street_suffixes = _EN_TYPES
    building_bases = _NAMES
    building_words = _EN_BUILDING_WORDS
    template_weights = {
        "number_street": 7, "street_only": 0.2, "house_name_street": 0.3, "building_number_street": 1.5,
        "flat_number_street": 3, "flat_in_building": 1.5, "floor_number_street": 1.5, "po_box": 0.7,
    }

    room_after_street = True
    street_abbreviations = {"Street": ("St",), "Avenue": ("Ave",), "Road": ("Rd",), "Drive": ("Dr",), "Lane": ("Ln",),
                            "Crescent": ("Cres",), "Boulevard": ("Blvd",), "Court": ("Ct",), "Place": ("Pl",)}
    room_abbreviations = {"Suite": ("Ste",)}
    street_words = frozenset(w.casefold() for w in _STREET_WORDS)
    building_word_set = _BUILDING_WORDS
    protected_words = street_words | _BUILDING_WORDS | {d.casefold() for d in _EN_DIRECTIONS + _FR_DIRECTIONS}
    room_pattern = r"(Unit|Suite|Ste|App\.|Bureau) \d+"
    floor_pattern = r"(\d+(st|nd|rd|th) Floor|\d+e étage)"
    po_box_pattern = r"(PO Box|C\.P\.) \d+"
    building_number_pattern = r"\d+"
    postcode_pattern = r"[A-Z]\d[A-Z] ?\d[A-Z]\d"
    region_pattern = "|".join(sorted({c for _, c, _, _, _ in TOWNS} | {n for _, _, n, _, _ in TOWNS}))

    def street_name(self, rng, fake, french: bool = False):
        if french:
            name = f"{_pick(rng, _FR_TYPES)} {rng.choice(_FR_BASES)}"
            return f"{name} {rng.choice(_FR_DIRECTIONS)}" if rng.random() < 0.2 else name
        base = self.surname(rng, fake) if rng.random() < 0.3 else rng.choice(_EN_BASES)
        name = f"{base} {_pick(rng, _EN_TYPES)}"
        return f"{name} {rng.choice(_EN_DIRECTIONS)}" if rng.random() < 0.2 else name

    def building_name(self, rng, fake):
        if rng.random() < 0.25:
            return f"{_pick(rng, _FR_BUILDING_WORDS)} {rng.choice(_NAMES)}"
        return f"{rng.choice(_NAMES)} {_pick(rng, _EN_BUILDING_WORDS)}"

    def building_number(self, rng):
        return str(rng.randint(1, 999) if rng.random() < 0.7 else rng.randint(1000, 9999))

    def room(self, rng):
        keyword = _pick(rng, (("Unit", 0.3), ("Suite", 0.3), ("App.", 0.2), ("Bureau", 0.2)))
        return f"{keyword} {rng.randint(100, 999) if keyword in ('Suite', 'Bureau') else rng.randint(1, 60)}"

    def floor(self, rng):
        n = rng.randint(1, 9)
        return f"{ordinal(n)} Floor" if rng.random() < 0.6 else f"{n}e étage"

    def po_box(self, rng):
        return f"PO Box {rng.randint(1, 99999)}" if rng.random() < 0.6 else f"C.P. {rng.randint(1, 99999)}"

    def is_street_name(self, text):
        return any(w.rstrip(".").casefold() in self.street_words for w in text.split(" "))

    def town_block(self, rng: random.Random, difficulty: str, want_locality: bool) -> TownBlock:
        # The two French-speaking towns carry extra weight so about a quarter of addresses are in French.
        town, code, name, fsas, _ = rng.choices(TOWNS, weights=[2.5 if t[4] else 1 for t in TOWNS])[0]
        postcode = f"{rng.choice(fsas)} {rng.randint(0, 9)}{rng.choice(_LDU_LETTERS)}{rng.randint(0, 9)}"
        province = code if rng.random() < 0.5 else name
        return TownBlock([[Part("TwnNm", town, comma_after=rng.random() < 0.5), Part("CtrySubDvsn", province),
                           Part("PstCd", postcode)]], set())

    def make_truth(self, rng, difficulty):
        """Streets in French-speaking towns are written in French; the street name needs the town, so it is set here."""
        truth = super().make_truth(rng, difficulty)
        town = next(p.text for seg in truth.segments for p in seg if p.field == "TwnNm")
        if next(t[4] for t in TOWNS if t[0] == town):
            for seg in truth.segments:
                for part in seg:
                    if part.field == "StrtNm":
                        part.text = self.street_name(rng, self.fake(rng), french=True)
        return truth

    def split_postcode(self, postcode):
        parts = postcode.split(" ")
        return (parts[0], parts[1]) if len(parts) == 2 else None

    def known_towns(self):
        return frozenset(t[0].casefold() for t in TOWNS)
