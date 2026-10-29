"""Germany: building number after the street, compound street names, postcode before the town (guide section 14)."""
from __future__ import annotations

import random

from addrgen.countries.base import CountryModule, _pick, register
from addrgen.model import Part, TownBlock

# (town, three-digit postcode prefixes); the last two digits are random.
TOWNS = (
    ("Berlin", ("101", "104", "107", "109", "120", "130")), ("Hamburg", ("200", "201", "203", "220")),
    ("München", ("803", "805", "810", "812")), ("Köln", ("506", "507", "509")),
    ("Frankfurt am Main", ("603", "604", "608")), ("Stuttgart", ("701", "703")), ("Düsseldorf", ("402", "404")),
    ("Leipzig", ("041", "042")), ("Dresden", ("010", "011")), ("Bremen", ("281", "282")), ("Hannover", ("301", "304")),
    ("Nürnberg", ("904", "905")), ("Bonn", ("531", "533")), ("Münster", ("481", "483")),
    ("Heidelberg", ("691", "692")), ("Freiburg im Breisgau", ("790", "791")),
)

_STEMS = ("Haupt", "Bahnhofs", "Schiller", "Goethe", "Linden", "Garten", "Kirch", "Markt", "Schul", "Berg", "Wald",
          "Mühlen", "Lessing", "Bismarck", "Rosen", "Eichen", "Dorf", "Park")
# (ending, weight): written lower case and joined to the stem ("Hauptstraße").
_ENDINGS = (("straße", 0.50), ("strasse", 0.10), ("weg", 0.12), ("allee", 0.06), ("platz", 0.05), ("gasse", 0.05),
            ("ring", 0.03), ("damm", 0.02), ("ufer", 0.02))
_CITY_ADJECTIVES = ("Berliner", "Münchner", "Hamburger", "Kölner", "Frankfurter", "Leipziger")
_SEPARATE = (("Straße", 0.6), ("Allee", 0.2), ("Platz", 0.1), ("Ring", 0.1))
_BUILDING_NAMES = ("Sonnenschein", "Waldblick", "Bergblick", "Lindenhof", "Rosengarten", "Hansa", "Merkur", "Atlas")
_ENDING_WORDS = frozenset({"straße", "strasse", "str", "weg", "allee", "platz", "gasse", "ring", "damm", "ufer"})
_BUILDING_WORDS = frozenset({"haus", "gebäude", "turm", "center"})


@register
class Germany(CountryModule):
    code = "DE"
    locale = "de_DE"
    country_names = ("Deutschland", "Germany")
    street_bases = _STEMS
    street_suffixes = _ENDINGS
    building_bases = _BUILDING_NAMES
    building_words = (("Haus", 0.4), ("Gebäude", 0.3), ("Turm", 0.1), ("Center", 0.2))
    template_weights = {
        "number_street": 7, "street_only": 0.2, "house_name_street": 0.5, "building_number_street": 1.5,
        "flat_number_street": 2.5, "flat_in_building": 1.5, "floor_number_street": 2, "po_box": 0.8,
    }

    number_first = False  # "Hauptstraße 12"
    room_after_street = True
    postcode_has_space = False
    can_drop_postcode_space = False
    street_abbreviations = {}
    room_abbreviations = {}
    street_endings = ("straße", "strasse", "weg", "allee", "platz", "gasse", "ring", "damm", "ufer")
    street_words = _ENDING_WORDS
    building_word_set = _BUILDING_WORDS
    protected_words = _ENDING_WORDS | _BUILDING_WORDS
    room_pattern = r"(Wohnung|Whg\.|Zimmer|Büro) \d+"
    floor_pattern = r"(\d\. OG|EG|Erdgeschoss|\d\. Etage)"
    po_box_pattern = r"Postfach \d+"
    building_number_pattern = r"\d+([a-z]|-\d+)?"
    postcode_pattern = r"\d{5}"

    def street_name(self, rng, fake):
        if rng.random() < 0.15:  # two words: "Berliner Straße"
            return f"{rng.choice(_CITY_ADJECTIVES)} {_pick(rng, _SEPARATE)}"
        stem = self.surname(rng, fake) if rng.random() < 0.3 else rng.choice(_STEMS)
        return f"{stem}{_pick(rng, _ENDINGS)}"

    def building_name(self, rng, fake):
        word = _pick(rng, self.building_words)
        if word == "Haus":
            return f"Haus {rng.choice(_BUILDING_NAMES)}"
        if word == "Gebäude":
            return f"Gebäude {rng.choice('ABCDEF')}"
        if word == "Turm":
            return f"Turm {rng.choice(('Nord', 'Süd', 'Ost', 'West'))}"
        return f"{rng.choice(_BUILDING_NAMES)} Center"

    def building_number(self, rng):
        n = rng.randint(1, 199)
        roll = rng.random()
        if roll < 0.15:
            return f"{n}{rng.choice('abcd')}"
        return f"{n}-{n + 2}" if roll < 0.20 else str(n)

    def room(self, rng):
        roll, n = rng.random(), rng.randint(1, 60)
        keyword = "Wohnung" if roll < 0.5 else "Büro" if roll < 0.7 else "Zimmer" if roll < 0.85 else "Whg."
        return f"{keyword} {n}"

    def floor(self, rng):
        roll, n = rng.random(), rng.randint(1, 6)
        return f"{n}. OG" if roll < 0.4 else "EG" if roll < 0.55 else "Erdgeschoss" if roll < 0.7 else f"{n}. Etage"

    def po_box(self, rng):
        return f"Postfach {rng.randint(1, 999999)}"

    def abbreviate_street(self, text, rng):
        """Straße or Strasse becomes Str.: as an ending ("Hauptstr.") or as a separate word ("Berliner Str.")."""
        words = text.split(" ")
        last = words[-1]
        for ending in ("straße", "strasse"):
            if last.casefold() == ending:
                words[-1] = "Str."
                return " ".join(words)
            if last.casefold().endswith(ending) and len(last) > len(ending):
                words[-1] = last[:-len(ending)] + "str."
                return " ".join(words)
        return text

    def abbreviation_tokens(self):
        return frozenset({"STR"})

    def is_street_name(self, text):
        last = text.split(" ")[-1].rstrip(".").casefold()
        return any(last.endswith(e) for e in _ENDING_WORDS)

    def town_block(self, rng: random.Random, difficulty: str, want_locality: bool) -> TownBlock:
        town, prefixes = rng.choice(TOWNS)
        postcode = f"{rng.choice(prefixes)}{rng.randint(0, 99):02d}"
        return TownBlock([[Part("PstCd", postcode), Part("TwnNm", town)]], set())

    def split_postcode(self, postcode):
        return None

    def known_towns(self):
        return frozenset(t.casefold() for t, _ in TOWNS)
