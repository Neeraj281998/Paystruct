"""Netherlands: number after the street, compound street names, postcode like 1234 AB before the town (guide section 15)."""
from __future__ import annotations

import random

from addrgen.countries.base import CountryModule, _pick, register
from addrgen.model import Part, TownBlock

# (town, lowest and highest four-digit postcode of its range)
TOWNS = (
    ("Amsterdam", 1011, 1109), ("Rotterdam", 3011, 3088), ("Den Haag", 2511, 2597), ("Utrecht", 3511, 3584),
    ("Eindhoven", 5611, 5658), ("Groningen", 9711, 9747), ("Tilburg", 5011, 5049), ("Almere", 1311, 1359),
    ("Breda", 4811, 4837), ("Nijmegen", 6511, 6546), ("Haarlem", 2011, 2036), ("Arnhem", 6811, 6846),
    ("Maastricht", 6211, 6229), ("Leiden", 2311, 2334), ("Zwolle", 8011, 8043), ("Delft", 2611, 2629),
)
# The letters a Dutch postcode may use.
_LETTERS = "ABCDEGHJKLMNPRSTVWXZ"

_STEMS = ("Keizers", "Heren", "Prinsen", "Kerk", "Molen", "Brouwers", "Beurs", "Stations", "Julian", "Wilhelmina", "Dorps",
          "School", "Markt", "Haven", "Nieuwe", "Oude")
_ENDINGS = (("straat", 0.45), ("laan", 0.15), ("weg", 0.12), ("gracht", 0.06), ("plein", 0.05), ("kade", 0.05),
            ("singel", 0.04), ("dijk", 0.03), ("steeg", 0.03), ("hof", 0.01), ("pad", 0.01))
_ENDING_WORDS = frozenset(e for e, _ in _ENDINGS)
_BUILDING_WORDS = frozenset({"gebouw", "toren"})


@register
class Netherlands(CountryModule):
    code = "NL"
    locale = "nl_NL"
    country_names = ("Nederland", "The Netherlands", "Netherlands", "Holland")
    street_bases = _STEMS
    street_suffixes = _ENDINGS
    building_bases = ("Zuid", "Noord", "Oost", "West", "Centrum")
    building_words = (("Gebouw", 0.8), ("Toren", 0.2))
    template_weights = {
        "number_street": 7, "house_name_street": 0.2, "building_number_street": 1, "flat_number_street": 2,
        "floor_number_street": 1.5, "flat_in_building": 1, "po_box": 0.8,
    }

    number_first = False  # "Keizersgracht 99"
    room_after_street = True
    street_abbreviations = {}
    room_abbreviations = {}
    street_endings = tuple(_ENDING_WORDS)
    street_words = _ENDING_WORDS
    building_word_set = _BUILDING_WORDS
    protected_words = _ENDING_WORDS | _BUILDING_WORDS | {"van"}
    room_pattern = r"(Unit|Kamer) \d+"
    floor_pattern = r"(\d+e etage|Begane grond)"
    po_box_pattern = r"Postbus \d+"
    building_number_pattern = r"\d+([A-D]|-\d)?"
    postcode_pattern = r"\d{4} ?[A-Z]{2}"

    def street_name(self, rng, fake):
        ending = _pick(rng, _ENDINGS)
        if rng.random() < 0.2 and ending in ("straat", "laan", "weg"):
            return f"Van {self.surname(rng, fake)}{ending}"  # "Van Baerlestraat"
        stem = self.surname(rng, fake) if rng.random() < 0.3 else rng.choice(_STEMS)
        return f"{stem}{ending}"

    def building_name(self, rng, fake):
        word = _pick(rng, self.building_words)
        return f"{word} {rng.choice('ABCDEF')}" if rng.random() < 0.6 else f"{word} {rng.choice(self.building_bases)}"

    def building_number(self, rng):
        n = rng.randint(1, 299)
        roll = rng.random()
        if roll < 0.12:
            return f"{n}{rng.choice('ABCD')}"
        return f"{n}-{rng.randint(1, 9)}" if roll < 0.20 else str(n)

    def room(self, rng):
        return f"Unit {rng.randint(1, 40)}" if rng.random() < 0.6 else f"Kamer {rng.randint(1, 40)}"

    def floor(self, rng):
        return "Begane grond" if rng.random() < 0.3 else f"{rng.randint(1, 6)}e etage"

    def po_box(self, rng):
        return f"Postbus {rng.randint(1, 99999)}"

    def is_street_name(self, text):
        return text.split(" ")[-1].casefold().endswith(tuple(_ENDING_WORDS))

    def town_block(self, rng: random.Random, difficulty: str, want_locality: bool) -> TownBlock:
        town, low, high = rng.choice(TOWNS)
        postcode = f"{rng.randint(low, high)} {rng.choice(_LETTERS)}{rng.choice(_LETTERS)}"
        return TownBlock([[Part("PstCd", postcode), Part("TwnNm", town)]], set())

    def split_postcode(self, postcode):
        parts = postcode.split(" ")
        return (parts[0], parts[1]) if len(parts) == 2 else None

    def known_towns(self):
        return frozenset(t.casefold() for t, _, _ in TOWNS)
