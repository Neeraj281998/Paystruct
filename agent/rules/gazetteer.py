"""GeoNames cities500 gazetteer, loaded once into memory. Read-only input (CC BY 4.0, https://www.geonames.org).

It only checks a town that is written in the text; it never supplies one (labelling guide section 20).
"""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from agent.rules.xsd import REPO_ROOT

GAZETTEER_PATH = REPO_ROOT / "service/src/main/resources/gazetteer/cities500.txt"


def fold(text: str) -> str:
    """Casefold, strip accents, turn punctuation into single spaces. 'St. John's' and 'st johns' fold alike."""
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("ß", "ss")
    text = re.sub(r"['’`]", "", text)
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return text.strip()


@dataclass(frozen=True)
class Place:
    name: str
    country: str
    admin1: str
    population: int


class Gazetteer:
    def __init__(self) -> None:
        self._by_country: dict[str, dict[str, Place]] = {}
        self._admin1: dict[str, dict[str, set[str]]] = {}

    def add(self, country: str, alias: str, place: Place) -> None:
        key = fold(alias)
        if not key:
            return
        table = self._by_country.setdefault(country, {})
        self._admin1.setdefault(country, {}).setdefault(key, set()).add(place.admin1)
        current = table.get(key)
        if current is None or place.population > current.population:
            table[key] = place

    def lookup(self, country: str, phrase: str) -> Place | None:
        return self._by_country.get(country, {}).get(fold(phrase))

    def admin1_codes(self, country: str, phrase: str) -> set[str]:
        """Every first-level region the name is listed under (many towns share a name)."""
        return self._admin1.get(country, {}).get(fold(phrase), set())

    def countries(self) -> list[str]:
        return sorted(self._by_country)

    def __len__(self) -> int:
        return sum(len(t) for t in self._by_country.values())


def load(path: Path = GAZETTEER_PATH, countries: set[str] | None = None) -> Gazetteer:
    gaz = Gazetteer()
    if not path.exists():
        return gaz
    with open(path, encoding="utf-8") as f:
        for line in f:
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 15 or (countries and cols[8] not in countries):
                continue
            place = Place(cols[1], cols[8], cols[10], int(cols[14] or 0))
            for alias in {cols[1], cols[2], *cols[3].split(",")}:
                if alias and alias.isascii() or alias in (cols[1], cols[2]):
                    gaz.add(cols[8], alias, place)
    return gaz


@lru_cache(maxsize=1)
def default_gazetteer() -> Gazetteer:
    from agent.rules.profile import all_profiles
    return load(countries=set(all_profiles()))


def log_population(place: Place | None) -> float:
    return math.log10(place.population + 1) if place else 0.0
