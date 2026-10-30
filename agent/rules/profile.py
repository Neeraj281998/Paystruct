"""Country profiles: one YAML file per country in agent/rules/countries/. Adding a country means adding a file."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from agent.rules.gazetteer import fold

COUNTRIES_DIR = Path(__file__).resolve().parent / "countries"


def _rx(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE | re.UNICODE)


@dataclass
class Region:
    name: str
    abbr: list[str]
    keys: set[str] = field(default_factory=set)  # folded name and abbreviations


@dataclass
class Profile:
    code: str
    raw: dict
    names: list[str]
    postcode_patterns: list[re.Pattern]
    partial_patterns: list[re.Pattern]
    postcode_max_tokens: int
    postcode_unique: bool
    number_position: str
    number_re: re.Pattern
    number_suffix_words: set[str]
    bldgnb_patterns: list[re.Pattern]
    street_words_after: set[str]
    street_words_before: set[str]
    street_suffixes: list[str]
    street_trailing: set[str]
    street_leading: set[str]
    street_particles: set[str]
    building_words: list[str]
    unit_patterns: list[re.Pattern]
    floor_patterns: list[re.Pattern]
    pobox_patterns: list[re.Pattern]
    landmark_keywords: list[str]
    landmark_suffixes: list[str]
    regions: list[Region]
    region_prefixes: set[str]
    region_requires_prefix: bool
    town_suffixes: list[dict]
    localities: bool
    locality_patterns: list[re.Pattern]
    unit_prefix_number: bool
    admin1_is_abbr: bool
    cue_words: set[str]

    def region_lookup(self) -> dict[str, Region]:
        table: dict[str, Region] = {}
        for r in self.regions:
            for k in r.keys:
                table.setdefault(k, r)
        return table


def _fold_words(items) -> set[str]:
    return {fold(i) for i in items or []}


def _build(data: dict) -> Profile:
    pc = data.get("postcode", {})
    st = data.get("street", {})
    rg = data.get("region", {})
    regions = []
    for e in rg.get("entries", []) or []:
        if isinstance(e, str):
            e = {"name": e}
        abbr = list(e.get("abbr", []) or [])
        regions.append(Region(e["name"], abbr, {fold(e["name"]), *(fold(a) for a in abbr)}))
    town = data.get("town", {})
    return Profile(
        code=data["code"], raw=data, names=list(data.get("names", [])),
        postcode_patterns=[_rx(p) for p in pc.get("patterns", [])],
        partial_patterns=[_rx(p) for p in pc.get("partial_patterns", [])],
        postcode_max_tokens=int(pc.get("max_tokens", 2)), postcode_unique=bool(pc.get("unique", False)),
        number_position=data.get("number_position", "before"),
        number_re=_rx(data.get("number_regex", r"\d+[A-Za-z]?(?:[-/]\d+[A-Za-z]?)?")),
        number_suffix_words=_fold_words(data.get("number_suffix_words")),
        bldgnb_patterns=[_rx(p) for p in data.get("bldgnb_patterns", [])],
        street_words_after=_fold_words(st.get("words_after")), street_words_before=_fold_words(st.get("words_before")),
        street_suffixes=[fold(s) for s in st.get("suffixes", [])],
        street_trailing=_fold_words(st.get("trailing")), street_leading=_fold_words(st.get("leading")), street_particles=_fold_words(st.get("particles")),
        building_words=[fold(w) for w in data.get("building_words", [])],
        unit_patterns=[_rx(p) for p in data.get("unit_patterns", [])],
        floor_patterns=[_rx(p) for p in data.get("floor_patterns", [])],
        pobox_patterns=[_rx(p) for p in data.get("pobox_patterns", [])],
        landmark_keywords=[fold(w) for w in data.get("landmark_keywords", [])],
        landmark_suffixes=[fold(w) for w in data.get("landmark_suffixes", [])],
        regions=regions, region_prefixes=_fold_words(rg.get("prefixes")),
        region_requires_prefix=bool(rg.get("requires_prefix", False)),
        town_suffixes=[{"re": _rx(s["pattern"]), "towns": _fold_words(s.get("towns")), "tokens": int(s.get("tokens", 1))}
                       for s in town.get("suffixes", [])],
        localities=bool(data.get("localities", False)),
        locality_patterns=[_rx(p) for p in data.get("locality_patterns", [])],
        unit_prefix_number=bool(data.get("unit_prefix_number", False)),
        admin1_is_abbr=bool(data.get("admin1_is_abbr", False)),
        cue_words=_fold_words(data.get("cue_words")),
    )


@lru_cache(maxsize=1)
def all_profiles(directory: Path = COUNTRIES_DIR) -> dict[str, Profile]:
    profiles: dict[str, Profile] = {}
    for path in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        profiles[data["code"]] = _build(data)
    return profiles


def load_profiles(directory: Path) -> dict[str, Profile]:
    """Uncached loader, for tests with a profile directory of their own."""
    return all_profiles.__wrapped__(directory)
