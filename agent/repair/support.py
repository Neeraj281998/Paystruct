"""How well a field value is supported: the same standard the rules engine uses (explicit evidence vs elimination).

A value is EXPLICIT when a postcode pattern, a keyword pattern, a word list of the country profile or the gazetteer says
it is that kind of thing. Otherwise it is ELIMINATION: a value nothing recognises. Nobody auto-accepts such a value,
neither the rules nor the model. UNCHECKED means the gazetteer is not loaded, so the town cannot be checked.
"""
from __future__ import annotations

import re

from agent.rules.base import building_word_hit, is_street_word
from agent.rules.gazetteer import Gazetteer, fold
from agent.rules.profile import Profile
from agent.rules.state import Token

EXPLICIT, ELIMINATION, UNCHECKED = "explicit", "elimination", "unchecked"
_ORDINAL = re.compile(r"\d+(?:st|nd|rd|th|e|er|re|ème|eme|de|ste|°)?|\d+", re.IGNORECASE)


def _tokens(value: str) -> list[Token]:
    return [Token(i, w, 0, 0, 0, 0, fold(w)) for i, w in enumerate(value.replace(",", " ").split())]


def gazetteer_loaded(gaz: Gazetteer | None) -> bool:
    return gaz is not None and len(gaz) > 0


def town_in_gazetteer(value: str, country: str, gaz: Gazetteer, profile: Profile | None) -> bool:
    """The written town, or the town without its written suffix ("Dublin 16", "BREST CEDEX 17", "Paris 13e")."""
    if gaz.lookup(country, value):
        return True
    words = value.split()
    if profile is not None:
        for suf in profile.town_suffixes:
            for k in range(min(suf["tokens"], len(words) - 1), 0, -1):
                if suf["re"].fullmatch(" ".join(words[-k:])):
                    base = " ".join(words[:-k])
                    if (not suf["towns"] or fold(base) in suf["towns"]) and gaz.lookup(country, base):
                        return True
    return False


def field_support(name: str, value: str, country: str, profile: Profile | None, gaz: Gazetteer | None) -> str:
    if profile is None or name == "Ctry":
        return EXPLICIT if name == "Ctry" else ELIMINATION
    toks = _tokens(value)
    if name == "PstCd":
        return EXPLICIT if any(p.fullmatch(value.strip()) for p in profile.postcode_patterns) else ELIMINATION
    if name == "TwnNm":
        if not gazetteer_loaded(gaz):
            return UNCHECKED
        return EXPLICIT if town_in_gazetteer(value, country, gaz, profile) else ELIMINATION
    if name == "TwnLctnNm":
        if any(p.fullmatch(value.strip()) for p in profile.locality_patterns):
            return EXPLICIT
        if not gazetteer_loaded(gaz):
            return UNCHECKED
        return EXPLICIT if gaz.lookup(country, value) else ELIMINATION
    if name == "CtrySubDvsn":
        table = profile.region_lookup()
        folds = [t.fold for t in toks]
        if " ".join(folds) in table and not profile.region_requires_prefix:
            return EXPLICIT
        if profile.region_prefixes and len(folds) > 1 and folds[0] in profile.region_prefixes and " ".join(folds[1:]) in table:
            return EXPLICIT
        return ELIMINATION
    if name in ("Room", "Flr", "PstBx"):
        patterns = {"Room": profile.unit_patterns, "Flr": profile.floor_patterns, "PstBx": profile.pobox_patterns}[name]
        return EXPLICIT if any(p.fullmatch(value.strip()) for p in patterns) else ELIMINATION
    if name == "BldgNb":
        v = value.strip()
        if profile.number_re.fullmatch(v) or any(p.fullmatch(v) for p in profile.bldgnb_patterns):
            return EXPLICIT
        if len(toks) == 2 and profile.number_re.fullmatch(toks[0].text) and toks[1].fold in profile.number_suffix_words:
            return EXPLICIT
        return ELIMINATION
    if name == "BldgNm":
        return EXPLICIT if building_word_hit(profile, [t.fold for t in toks]) else ELIMINATION
    if name == "StrtNm":
        if not any(is_street_word(profile, t) for t in toks):
            return ELIMINATION
        odd = [t.text for t in toks if any(c.isdigit() for c in t.text) and not _ORDINAL.fullmatch(t.text)]
        return ELIMINATION if odd else EXPLICIT
    return ELIMINATION


def unsupported_fields(fields: dict[str, str], country: str | None, profile: Profile | None, gaz: Gazetteer | None) -> tuple[list[str], bool]:
    """(fields with no support, whether any check could not be made because the gazetteer is not loaded)."""
    bad, unchecked = [], False
    for name, value in fields.items():
        if name == "Ctry":
            continue
        s = field_support(name, value, country or "", profile, gaz)
        if s == ELIMINATION:
            bad.append(name)
        elif s == UNCHECKED:
            unchecked = True
    return bad, unchecked
