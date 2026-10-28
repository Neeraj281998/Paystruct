"""The country module contract and the address templates shared by every country.

Adding a country means adding one module in this package that subclasses CountryModule and is decorated with
@register. The registry discovers it by importing every module here; nothing else changes.
"""
from __future__ import annotations

import random
import string
from abc import ABC, abstractmethod
from typing import ClassVar

from faker import Faker

from addrgen.model import Part, TownBlock, Truth

_REGISTRY: dict[str, "CountryModule"] = {}

# Templates a difficulty tier may use. Easy stays plain; hard may use anything. (The tier an address finally gets is
# computed from its tags, see difficulty.py, so these only shape the mix.)
EASY_TEMPLATES = ("number_street", "po_box")
MEDIUM_TEMPLATES = EASY_TEMPLATES + (
    "street_only", "house_name_street", "building_street_number", "flat_number_street", "floor_number_street",
    "locality_number_street",
)
HARD_TEMPLATES = MEDIUM_TEMPLATES + ("flat_in_building", "unit_business_park", "rural_house")
TEMPLATES_BY_DIFFICULTY = {"easy": EASY_TEMPLATES, "medium": MEDIUM_TEMPLATES, "hard": HARD_TEMPLATES}

_ROOM_KEYWORDS = (("Flat", 0.30), ("Apartment", 0.30), ("Unit", 0.25), ("Suite", 0.10), ("Room", 0.05))
_ORDINALS = {1: "1st", 2: "2nd", 3: "3rd"}


def register(cls):
    _REGISTRY[cls.code] = cls()
    return cls


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


class CountryModule(ABC):
    code: ClassVar[str]  # ISO 3166 alpha-2, the gold Ctry
    locale: ClassVar[str]  # Faker locale, used for surnames in street and building names
    country_names: ClassVar[tuple[str, ...]]  # ways the country is written other than its code
    street_bases: ClassVar[tuple[str, ...]]
    street_suffixes: ClassVar[tuple[tuple[str, float], ...]]
    building_bases: ClassVar[tuple[str, ...]]
    building_words: ClassVar[tuple[tuple[str, float], ...]]
    place_names: ClassVar[tuple[str, ...]]  # used in business park names
    template_weights: ClassVar[dict[str, float]]

    _fake: Faker | None = None

    # ---- hooks a country must provide -------------------------------------------------------------------------
    @abstractmethod
    def town_block(self, rng: random.Random, difficulty: str, want_locality: bool) -> TownBlock:
        """Locality, town plus postcode and county lines. Postal districts only when difficulty is hard."""

    @abstractmethod
    def split_postcode(self, postcode: str) -> tuple[str, str] | None:
        """The two halves a postcode can be split into, or None if it has no natural split."""

    # ---- shared machinery ------------------------------------------------------------------------------------
    def fake(self, rng: random.Random) -> Faker:
        if self._fake is None:
            self._fake = Faker(self.locale)
        self._fake.seed_instance(rng.getrandbits(64))
        return self._fake

    def make_truth(self, rng: random.Random, difficulty: str) -> Truth:
        fake = self.fake(rng)
        allowed = [t for t in TEMPLATES_BY_DIFFICULTY[difficulty] if t in self.template_weights]
        name = rng.choices(allowed, weights=[self.template_weights[t] for t in allowed])[0]
        street_side, want_locality = _TEMPLATES[name](self, rng, fake)
        block = self.town_block(rng, difficulty, want_locality)
        segments = street_side + block.segments
        fields = {p.field for seg in segments for p in seg}
        return Truth(self.code, name, segments, structure_tags(fields) | block.tags)

    def street_name(self, rng: random.Random, fake: Faker) -> str:
        base = fake.last_name() if rng.random() < 0.4 else rng.choice(self.street_bases)
        suffix = rng.choices([s for s, _ in self.street_suffixes], weights=[w for _, w in self.street_suffixes])[0]
        return f"{base} {suffix}"

    def building_name(self, rng: random.Random, fake: Faker) -> str:
        base = fake.last_name() if rng.random() < 0.4 else rng.choice(self.building_bases)
        word = rng.choices([w for w, _ in self.building_words], weights=[x for _, x in self.building_words])[0]
        return f"{base} {word}"

    def business_park(self, rng: random.Random, long: bool = False) -> str:
        place = rng.choice(self.place_names)
        name = f"{place} Business Park"
        if long:
            name += " and Enterprise Centre"
        if rng.random() < 0.6:
            name = f"Block {rng.choice('ABCDEFGH')} {name}"
        return name


# ---- values -----------------------------------------------------------------------------------------------------
def building_number(rng: random.Random) -> str:
    n = rng.randint(1, 199)
    roll = rng.random()
    if roll < 0.15:
        return f"{n}{rng.choice('ABCD')}"
    if roll < 0.20:
        return f"{n}-{n + 2}"
    return str(n)


def room(rng: random.Random) -> str:
    keyword = rng.choices([k for k, _ in _ROOM_KEYWORDS], weights=[w for _, w in _ROOM_KEYWORDS])[0]
    if keyword == "Flat" and rng.random() < 0.3:
        return f"Flat {rng.choice(string.ascii_uppercase[:6])}"
    n = rng.randint(1, 60)
    return f"{keyword} {n}{rng.choice('ABC')}" if rng.random() < 0.2 else f"{keyword} {n}"


def floor(rng: random.Random) -> str:
    roll = rng.random()
    if roll < 0.2:
        return "Ground Floor"
    if roll < 0.3:
        return "Basement"
    n = rng.randint(1, 9)
    return f"Floor {n}" if roll < 0.5 else f"{_ORDINALS.get(n, f'{n}th')} Floor"


def po_box(rng: random.Random) -> str:
    n = rng.randint(1, 99999)
    return f"PO Box {n}" if rng.random() < 0.7 else f"P.O. Box {n}"


# ---- templates: each returns (street-side segments, whether the town block should include a locality) -----------
def _t_number_street(m, rng, fake):
    return [[Part("BldgNb", building_number(rng)), Part("StrtNm", m.street_name(rng, fake))]], False


def _t_street_only(m, rng, fake):
    return [[Part("StrtNm", m.street_name(rng, fake))]], False


def _t_house_name_street(m, rng, fake):
    return [[Part("BldgNm", m.building_name(rng, fake))], [Part("StrtNm", m.street_name(rng, fake))]], False


def _t_building_street_number(m, rng, fake):
    return [[Part("BldgNb", building_number(rng)), Part("BldgNm", m.building_name(rng, fake))],
            [Part("StrtNm", m.street_name(rng, fake))]], False


def _t_flat_number_street(m, rng, fake):
    return [[Part("Room", room(rng))],
            [Part("BldgNb", building_number(rng)), Part("StrtNm", m.street_name(rng, fake))]], False


def _t_flat_in_building(m, rng, fake):
    street = [Part("StrtNm", m.street_name(rng, fake))]
    if rng.random() < 0.7:
        street.insert(0, Part("BldgNb", building_number(rng)))
    return [[Part("Room", room(rng))], [Part("BldgNm", m.building_name(rng, fake))], street], False


def _t_floor_number_street(m, rng, fake):
    segments = [[Part("Flr", floor(rng))],
                [Part("BldgNb", building_number(rng)), Part("StrtNm", m.street_name(rng, fake))]]
    if rng.random() < 0.3:
        segments.insert(0, [Part("Room", room(rng))])
    return segments, False


def _t_unit_business_park(m, rng, fake):
    unit = Part("Room", f"Unit {rng.randint(1, 40)}")
    park = Part("BldgNm", m.business_park(rng, long=rng.random() < 0.4))
    return ([[unit, park]] if rng.random() < 0.5 else [[unit], [park]]), False


def _t_po_box(m, rng, fake):
    return [[Part("PstBx", po_box(rng))]], False


def _t_rural_house(m, rng, fake):
    return [[Part("BldgNm", m.building_name(rng, fake))]], True


def _t_locality_number_street(m, rng, fake):
    return [[Part("BldgNb", building_number(rng)), Part("StrtNm", m.street_name(rng, fake))]], True


_TEMPLATES = {
    "number_street": _t_number_street,
    "street_only": _t_street_only,
    "house_name_street": _t_house_name_street,
    "building_street_number": _t_building_street_number,
    "flat_number_street": _t_flat_number_street,
    "flat_in_building": _t_flat_in_building,
    "floor_number_street": _t_floor_number_street,
    "unit_business_park": _t_unit_business_park,
    "po_box": _t_po_box,
    "rural_house": _t_rural_house,
    "locality_number_street": _t_locality_number_street,
}
