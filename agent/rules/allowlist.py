"""Allowlisted abbreviation expansions (labelling guide sections 10 and 13-18).

Dependency-free on purpose: the scorer uses it now and the Day 4 grounding check imports it. Gold keeps abbreviations as
written; a system may output either form. These pairs are the only expansions a repair may add.
"""
from __future__ import annotations

import unicodedata

_EN_UK = {"st": "street", "rd": "road", "ave": "avenue", "dr": "drive", "ln": "lane", "ter": "terrace", "cl": "close",
          "sq": "square", "gdns": "gardens", "cres": "crescent", "apt": "apartment"}
_EN_NA = {"blvd": "boulevard", "ct": "court", "pl": "place", "ave": "avenue", "st": "street", "rd": "road", "dr": "drive",
          "ln": "lane", "cres": "crescent", "ste": "suite", "n": "north", "s": "south", "e": "east", "w": "west"}

# abbreviation (casefolded, no trailing dot) -> expansion (casefolded), per country
ABBREVIATIONS: dict[str, dict[str, str]] = {
    "IE": dict(_EN_UK),
    "GB": dict(_EN_UK),
    "FR": {"av": "avenue", "bd": "boulevard", "pl": "place", "ch": "chemin", "imp": "impasse", "all": "allée",
           "appt": "appartement", "bât": "bâtiment"},
    "DE": {},  # only the Str./Straße ending, handled in canonical()
    "NL": {},
    "CA": dict(_EN_NA),
    "US": {**_EN_NA, "apt": "apartment"},
    "IN": {"rd": "road", "apt": "apartment"},
}


def _fold(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold()


def _canonical_token(token: str, table: dict[str, str], german: bool) -> str:
    bare = token.strip(",;").rstrip(".")
    if german and len(bare) >= 3 and bare.endswith("str"):
        bare = bare[:-3] + "strasse"
    if bare in table:
        return table[bare]
    return bare


def canonical(value: str, country: str) -> str:
    """The value with every allowlisted abbreviation replaced by its expansion, casefolded, for comparison."""
    table = ABBREVIATIONS.get(country, {})
    german = country == "DE"
    tokens = [_canonical_token(t, table, german) for t in _fold(value).split()]
    return " ".join(tokens)


def equivalent(a: str, b: str, country: str) -> bool:
    """True when two values are equal after allowlisted abbreviation expansion."""
    return canonical(a, country) == canonical(b, country)


def expansions(country: str) -> dict[str, str]:
    """abbreviation -> expansion pairs for a country (copy)."""
    return dict(ABBREVIATIONS.get(country, {}))
