"""The country module contract and the address templates shared by every country.

Adding a country means adding one module in this package that subclasses CountryModule and is decorated with
@register. The registry discovers it by importing every module here; nothing else changes. A module supplies its data
and overrides only the hooks where its language or conventions differ from the defaults (which are IE and GB).
"""
from __future__ import annotations

import random
import re
import string
from abc import ABC, abstractmethod
from typing import ClassVar

from faker import Faker

from addrgen.model import Part, TownBlock, Truth
from addrgen.words import BUILDING_PHRASES, BUILDING_WORDS, ROOM_ABBREVIATIONS, STREET_ABBREVIATIONS, STREET_WORDS

_REGISTRY: dict[str, "CountryModule"] = {}

# Templates a difficulty tier may use. Easy stays plain; hard may use anything. (The tier an address finally gets is
# computed from its tags, see difficulty.py, so these only shape the mix.)
EASY_TEMPLATES = ("number_street", "po_box")
MEDIUM_TEMPLATES = EASY_TEMPLATES + (
    "street_only", "house_name_street", "building_street_number", "building_number_street", "flat_number_street",
    "floor_number_street", "locality_number_street",
)
HARD_TEMPLATES = MEDIUM_TEMPLATES + ("flat_in_building", "unit_business_park", "rural_house")
TEMPLATES_BY_DIFFICULTY = {"easy": EASY_TEMPLATES, "medium": MEDIUM_TEMPLATES, "hard": HARD_TEMPLATES}

_ROOM_KEYWORDS = (("Flat", 0.30), ("Apartment", 0.30), ("Unit", 0.25), ("Suite", 0.10), ("Room", 0.05))


def register(cls):
    _REGISTRY[cls.code] = cls()
    return cls


def ordinal(n: int) -> str:
    """1st, 2nd, 3rd, 4th, ... 11th, 12th, 13th, 21st."""
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def structure_tags(fields: set[str]) -> set[str]:
    """Structure tags of the labelling guide, section 11, derived from which fields an address has."""
    tags: set[str] = set()
    if "Room" in fields:
        tags.add("flat")
    if "BldgNm" in fields:
        tags.add("building_name")
    if "Flr" in fields:
        tags.add("floor")
    if "PstBx" in fields:
        tags.add("po_box")
    if "TwnLctnNm" in fields:
        tags.add("locality")
    if "CtrySubDvsn" in fields:
        tags.add("county")
    if ("StrtNm" in fields or "BldgNm" in fields) and "BldgNb" not in fields:
        tags.add("no_street_number")
    return tags


def _pick(rng: random.Random, weighted: tuple[tuple[str, float], ...]) -> str:
    return rng.choices([v for v, _ in weighted], weights=[w for _, w in weighted])[0]


class CountryModule(ABC):
    # ---- data a country must provide --------------------------------------------------------------------------
    code: ClassVar[str]  # ISO 3166 alpha-2, the gold Ctry
    locale: ClassVar[str]  # Faker locale, used for surnames only
    country_names: ClassVar[tuple[str, ...]]  # ways the country is written other than its code
    street_bases: ClassVar[tuple[str, ...]]
    street_suffixes: ClassVar[tuple[tuple[str, float], ...]]
    building_bases: ClassVar[tuple[str, ...]]
    building_words: ClassVar[tuple[tuple[str, float], ...]]
    place_names: ClassVar[tuple[str, ...]] = ()  # used in business park names (IE, GB)
    template_weights: ClassVar[dict[str, float]]

    # ---- conventions (defaults are IE and GB) -----------------------------------------------------------------
    number_first: ClassVar[bool] = True  # building number before the street name
    room_after_street: ClassVar[bool] = False  # flat or unit on a line after the street
    street_type_first: ClassVar[bool] = False  # "Rue des Tilleuls": the street word comes first
    postcode_has_space: ClassVar[bool | None] = True  # None: written either way as a natural variant
    can_drop_postcode_space: ClassVar[bool] = True  # postcode_no_space applies
    street_abbreviations: ClassVar[dict[str, tuple[str, ...]]] = STREET_ABBREVIATIONS
    room_abbreviations: ClassVar[dict[str, tuple[str, ...]]] = ROOM_ABBREVIATIONS
    street_endings: ClassVar[tuple[str, ...]] = ()  # compound street endings (DE, NL): a typo never touches these
    street_words: ClassVar[frozenset[str]] = frozenset(w.casefold() for w in STREET_WORDS)
    building_word_set: ClassVar[frozenset[str]] = frozenset(
        {w.casefold() for w in BUILDING_WORDS} | {p.casefold() for p in BUILDING_PHRASES})
    protected_words: ClassVar[frozenset[str]] = frozenset(
        {w.casefold() for w in STREET_WORDS | BUILDING_WORDS} | {w.casefold() for p in BUILDING_PHRASES for w in p.split()})

    # How each gold value must look, for the tests and the validator (case-insensitive full match).
    room_pattern: ClassVar[str] = r"(Flat|Apartment|Apt\.?|Unit|Suite|Room) \w+"
    floor_pattern: ClassVar[str] = r"(ground floor|basement|floor \d|\d(st|nd|rd|th) floor)"
    po_box_pattern: ClassVar[str] = r"(PO|P\.O\.) Box \d+"
    building_number_pattern: ClassVar[str] = r"\d+[A-D]?(-\d+)?"
    postcode_pattern: ClassVar[str]
    region_pattern: ClassVar[str | None] = None

    _fake: Faker | None = None

    # ---- hooks a country must provide -------------------------------------------------------------------------
    @abstractmethod
    def town_block(self, rng: random.Random, difficulty: str, want_locality: bool) -> TownBlock:
        """Locality, town plus postcode (and region) and county lines. Districts and Cedex only when hard."""

    @abstractmethod
    def split_postcode(self, postcode: str) -> tuple[str, str] | None:
        """The two halves a postcode can be split into, or None if it has no natural split."""

    @abstractmethod
    def known_towns(self) -> frozenset[str]:
        """Every town this module can write, case-folded."""

    # ---- shared machinery ------------------------------------------------------------------------------------
    def fake(self, rng: random.Random) -> Faker:
        if self._fake is None:
            self._fake = Faker(self.locale)
        self._fake.seed_instance(rng.getrandbits(64))
        return self._fake

    def make_truth(self, rng: random.Random, difficulty: str) -> Truth:
        fake = self.fake(rng)
        allowed = [t for t in TEMPLATES_BY_DIFFICULTY[difficulty] if self.template_weights.get(t, 0) > 0]
        name = rng.choices(allowed, weights=[self.template_weights[t] for t in allowed])[0]
        street_side, want_locality = _TEMPLATES[name](self, rng, fake)
        block = self.town_block(rng, difficulty, want_locality)
        segments = street_side + block.segments
        fields = {p.field for seg in segments for p in seg if p.field}
        return Truth(self.code, name, segments, structure_tags(fields) | block.tags)

    def surname(self, rng: random.Random, fake: Faker) -> str:
        """One clean capitalised surname word from Faker (Faker returns things like 'Koch II' or 'van der Sloot')."""
        for _ in range(5):
            for token in fake.last_name().split():
                if token.isalpha() and token[0].isupper() and len(token) >= 3:
                    return token
        return rng.choice(self.street_bases)

    # -- values: defaults are IE and GB, a country overrides what differs
    def street_name(self, rng: random.Random, fake: Faker) -> str:
        base = self.surname(rng, fake) if rng.random() < 0.4 else rng.choice(self.street_bases)
        return f"{base} {_pick(rng, self.street_suffixes)}"

    def building_name(self, rng: random.Random, fake: Faker) -> str:
        base = self.surname(rng, fake) if rng.random() < 0.4 else rng.choice(self.building_bases)
        return f"{base} {_pick(rng, self.building_words)}"

    def business_park(self, rng: random.Random, long: bool = False) -> str:
        place = rng.choice(self.place_names)
        name = f"{place} Business Park"
        if long:
            name += " and Enterprise Centre"
        if rng.random() < 0.6:
            name = f"Block {rng.choice('ABCDEFGH')} {name}"
        return name

    def building_number(self, rng: random.Random) -> str:
        n = rng.randint(1, 199)
        roll = rng.random()
        if roll < 0.15:
            return f"{n}{rng.choice('ABCD')}"
        if roll < 0.20:
            return f"{n}-{n + 2}"
        return str(n)

    def room(self, rng: random.Random) -> str:
        keyword = _pick(rng, _ROOM_KEYWORDS)
        if keyword == "Flat" and rng.random() < 0.3:
            return f"Flat {rng.choice(string.ascii_uppercase[:6])}"
        n = rng.randint(1, 60)
        return f"{keyword} {n}{rng.choice('ABC')}" if rng.random() < 0.2 else f"{keyword} {n}"

    def floor(self, rng: random.Random) -> str:
        roll = rng.random()
        if roll < 0.2:
            return "Ground Floor"
        if roll < 0.3:
            return "Basement"
        n = rng.randint(1, 9)
        return f"Floor {n}" if roll < 0.5 else f"{ordinal(n)} Floor"

    def po_box(self, rng: random.Random) -> str:
        n = rng.randint(1, 99999)
        return f"PO Box {n}" if rng.random() < 0.7 else f"P.O. Box {n}"

    def street_parts(self, rng: random.Random, fake: Faker, with_number: bool = True) -> list[Part]:
        """The street line: number and street name, in the country's order."""
        street = Part("StrtNm", self.street_name(rng, fake))
        if not with_number:
            return [street]
        number = Part("BldgNb", self.building_number(rng))
        return [number, street] if self.number_first else [street, number]

    # -- corruptions that depend on the language
    def abbreviate_street(self, text: str, rng: random.Random) -> str:
        words = text.split(" ")
        for i in ([0] if self.street_type_first else range(len(words) - 1, -1, -1)):
            if words[i] in self.street_abbreviations:
                words[i] = rng.choice(self.street_abbreviations[words[i]])
                return " ".join(words)
        return text

    def abbreviate_room(self, text: str, rng: random.Random) -> str:
        words = text.split(" ")
        if words[0] in self.room_abbreviations:
            words[0] = rng.choice(self.room_abbreviations[words[0]])
            return " ".join(words)
        return text

    def typo_spans(self, field: str, text: str) -> list[tuple[int, int]]:
        """Where in a street or building name a typo may go: a word of at least five letters, never a street or
        building word, and for compound names (DE, NL) only the stem before the street ending."""
        spans, pos = [], 0
        for word in text.split(" "):
            start, pos = pos, pos + len(word) + 1
            if not word.isalpha():
                continue
            lower = word.casefold()
            ending = next((e for e in self.street_endings if lower.endswith(e) and len(word) > len(e)), None)
            if ending:
                if len(word) - len(ending) >= 5:
                    spans.append((start, start + len(word) - len(ending)))
            elif len(word) >= 5 and lower not in self.protected_words:
                spans.append((start, start + len(word)))
        return spans

    # -- checks the tests and the validator use
    def is_street_name(self, text: str) -> bool:
        words = [w.rstrip(".").casefold() for w in text.split(" ")]
        return (words[0] if self.street_type_first else words[-1]) in self.street_words

    def is_building_name(self, text: str) -> bool:
        return any(w.rstrip(".").casefold() in self.building_word_set for w in text.split(" ")) or any(
            p.casefold() in text.casefold() for p in BUILDING_PHRASES)

    def is_known_town(self, text: str) -> bool:
        return text.casefold() in self.known_towns()

    def abbreviation_tokens(self) -> frozenset[str]:
        """Upper-case tokens (no full stop) that an abbreviation may write."""
        return frozenset(a.rstrip(".").upper() for table in (self.street_abbreviations, self.room_abbreviations)
                         for abbreviations in table.values() for a in abbreviations)

    def convention_problems(self, gold: dict[str, str]) -> list[str]:
        """How a gold value breaks this country's labelling conventions (guide sections 2-7 and 13-18)."""
        problems = []
        patterns = {"Room": self.room_pattern, "Flr": self.floor_pattern, "PstBx": self.po_box_pattern,
                    "BldgNb": self.building_number_pattern, "PstCd": self.postcode_pattern}
        for field, pattern in patterns.items():
            if field in gold and not re.fullmatch(pattern, gold[field], re.IGNORECASE):
                problems.append(f"{field} {gold[field]!r} does not look like a {self.code} {field}")
        if "StrtNm" in gold and not self.is_street_name(gold["StrtNm"]):
            problems.append(f"StrtNm {gold['StrtNm']!r} has no {self.code} street word")
        if "BldgNm" in gold and not self.is_building_name(gold["BldgNm"]):
            problems.append(f"BldgNm {gold['BldgNm']!r} has no {self.code} building word")
        if "TwnNm" in gold and not self.is_known_town(gold["TwnNm"]):
            problems.append(f"TwnNm {gold['TwnNm']!r} is not a known {self.code} town")
        if "CtrySubDvsn" in gold and self.region_pattern and not re.fullmatch(self.region_pattern, gold["CtrySubDvsn"], re.IGNORECASE):
            problems.append(f"CtrySubDvsn {gold['CtrySubDvsn']!r} is not a known {self.code} region")
        if gold.get("Ctry") != self.code:
            problems.append(f"Ctry is {gold.get('Ctry')!r}, not {self.code}")
        return problems


# ---- templates: each returns (street-side segments, whether the town block should include a locality) -------------
def _unit(m: CountryModule, core: list[list[Part]], unit: list[list[Part]]) -> list[list[Part]]:
    """Flat, unit or floor lines go before the street line, or after it in countries that write them second."""
    return core + unit if m.room_after_street else unit + core


def _t_number_street(m, rng, fake):
    return [m.street_parts(rng, fake)], False


def _t_street_only(m, rng, fake):
    return [m.street_parts(rng, fake, with_number=False)], False


def _t_house_name_street(m, rng, fake):
    return [[Part("BldgNm", m.building_name(rng, fake))], m.street_parts(rng, fake, with_number=False)], False


def _t_building_street_number(m, rng, fake):
    """IE and GB: a number before a building name, then the street ("14 Marlow Court, Riverside Road")."""
    return [[Part("BldgNb", m.building_number(rng)), Part("BldgNm", m.building_name(rng, fake))],
            m.street_parts(rng, fake, with_number=False)], False


def _t_building_number_street(m, rng, fake):
    """A building name line, then number and street."""
    return [[Part("BldgNm", m.building_name(rng, fake))], m.street_parts(rng, fake)], False


def _t_flat_number_street(m, rng, fake):
    return _unit(m, [m.street_parts(rng, fake)], [[Part("Room", m.room(rng))]]), False


def _t_flat_in_building(m, rng, fake):
    core = [[Part("BldgNm", m.building_name(rng, fake))], m.street_parts(rng, fake, with_number=rng.random() < 0.7)]
    return _unit(m, core, [[Part("Room", m.room(rng))]]), False


def _t_floor_number_street(m, rng, fake):
    unit = [[Part("Flr", m.floor(rng))]]
    if rng.random() < 0.3:
        unit.insert(0, [Part("Room", m.room(rng))])
    return _unit(m, [m.street_parts(rng, fake)], unit), False


def _t_unit_business_park(m, rng, fake):
    unit = Part("Room", f"Unit {rng.randint(1, 40)}")
    park = Part("BldgNm", m.business_park(rng, long=rng.random() < 0.4))
    return ([[unit, park]] if rng.random() < 0.5 else [[unit], [park]]), False


def _t_po_box(m, rng, fake):
    return [[Part("PstBx", m.po_box(rng))]], False


def _t_rural_house(m, rng, fake):
    return [[Part("BldgNm", m.building_name(rng, fake))]], True


def _t_locality_number_street(m, rng, fake):
    return [m.street_parts(rng, fake)], True


_TEMPLATES = {
    "number_street": _t_number_street,
    "street_only": _t_street_only,
    "house_name_street": _t_house_name_street,
    "building_street_number": _t_building_street_number,
    "building_number_street": _t_building_number_street,
    "flat_number_street": _t_flat_number_street,
    "flat_in_building": _t_flat_in_building,
    "floor_number_street": _t_floor_number_street,
    "unit_business_park": _t_unit_business_park,
    "po_box": _t_po_box,
    "rural_house": _t_rural_house,
    "locality_number_street": _t_locality_number_street,
}
