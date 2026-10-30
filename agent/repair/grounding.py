"""Grounding: every value of the output must be built from text in the original raw lines.

The only exceptions are the ISO country code (which must itself be derivable from the text or the hint) and the
abbreviation expansions in agent/rules/allowlist.py. Also: agreement with the rules' explicit fields, and a gazetteer check
of the written town (skipped, and marked unchecked, when the gazetteer is not loaded).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from agent.repair.support import gazetteer_loaded, town_in_gazetteer
from agent.repair.validator import Candidate
from agent.rules import allowlist
from agent.rules.gazetteer import Gazetteer, fold
from agent.rules.profile import Profile, all_profiles
from agent.rules.scoring import values_equal

UNGROUNDED_VALUE = "UNGROUNDED_VALUE"
UNGROUNDED_ADRLINE = "UNGROUNDED_ADRLINE"
UNGROUNDED_COUNTRY = "UNGROUNDED_COUNTRY"
CONTRADICTS_RULES = "CONTRADICTS_RULES"
TOWN_NOT_IN_GAZETTEER = "TOWN_NOT_IN_GAZETTEER"

_PUNCT = re.compile(r"[,;()\[\]\"“”]+")
# fields whose explicit evidence from the rules the model may not contradict
# Every field the rules set with explicit evidence is locked: the model may repeat it (or an allowlisted form of it), never change or delete it.
# A field the rules set by elimination is not locked: the model may place it differently, and the completeness check stops it vanishing.
AGREEMENT_FIELDS = ("PstCd", "TwnNm", "CtrySubDvsn", "Room", "Flr", "PstBx", "StrtNm", "BldgNb", "BldgNm", "TwnLctnNm")


@dataclass
class GroundingResult:
    reasons: list[str] = field(default_factory=list)
    unchecked: bool = False   # the gazetteer was not loaded, so the town was not checked

    @property
    def ok(self) -> bool:
        return not self.reasons


def _norm(text: str, country: str) -> str:
    text = unicodedata.normalize("NFC", _PUNCT.sub(" ", text))
    return allowlist.canonical(text, country)


def value_grounded(value: str, raw_lines: list[str], country: str, name: str = "") -> bool:
    """The value, normalised for case, whitespace and the allowed punctuation, occurs in the input (allowlisted expansions equal)."""
    text = _norm(" ".join(raw_lines), country)
    v = _norm(value, country)
    if not v:
        return False
    if name == "PstCd":
        return re.sub(r"\s+", "", v) in re.sub(r"\s+", "", text)
    return re.search(r"(?<!\w)" + re.escape(v) + r"(?!\w)", text) is not None


def words_grounded(value: str, raw_lines: list[str], country: str) -> bool:
    """AdrLine is unstructured text assembled from the input, possibly from pieces that are not next to each other:
    every word must be an input word (allowlisted expansions equal), nothing may be new."""
    text_words = set(_norm(" ".join(raw_lines), country).split())
    words = _norm(value, country).split()
    return bool(words) and all(w in text_words or w.strip("-/") in text_words or any(w in tw.replace("-", " ").replace("/", " ").split() for tw in text_words) for w in words)


def country_derivable(code: str, raw_lines: list[str], hint: str | None, profiles: dict[str, Profile] | None = None) -> bool:
    """Written country name or code, the message's country hint, or a postcode pattern unique to that country."""
    if hint and hint == code:
        return True
    profiles = profiles or all_profiles()
    prof = profiles.get(code)
    if prof is None:
        return False
    words = [w.strip(",;()") for line in raw_lines for w in line.split()]
    words = [w for w in words if w]
    all_lower = not any(c.isupper() for line in raw_lines for c in line)
    if any(w == code or (all_lower and w.upper() == code) for w in words):
        return True
    names = {fold(n) for n in prof.names}
    for n in range(1, 5):
        for i in range(len(words) - n + 1):
            if fold(" ".join(words[i:i + n])) in names:
                return True
    if prof.postcode_unique:
        for n in range(1, prof.postcode_max_tokens + 1):
            for i in range(len(words) - n + 1):
                chunk = " ".join(words[i:i + n])
                if any(p.fullmatch(chunk) for p in prof.postcode_patterns):
                    return True
    return False


def check(candidate: Candidate, raw_lines: list[str], country_hint: str | None = None, rules=None,
          gazetteer: Gazetteer | None = None, profiles: dict[str, Profile] | None = None) -> GroundingResult:
    profiles = profiles or all_profiles()
    res = GroundingResult()
    fields = candidate.fields
    ctry = fields.get("Ctry")
    country = ctry if ctry in profiles else ""
    for name, value in fields.items():
        if name == "Ctry":
            continue
        if not value_grounded(value, raw_lines, country, name):
            res.reasons.append(f"{UNGROUNDED_VALUE}:{name}")
    for line in candidate.adr_lines:
        if not words_grounded(line, raw_lines, country):
            res.reasons.append(UNGROUNDED_ADRLINE)
            break
    if ctry is not None and not country_derivable(ctry, raw_lines, country_hint, profiles):
        res.reasons.append(UNGROUNDED_COUNTRY)

    # agreement: a field the rules set with explicit evidence must not be contradicted by the model
    if rules is not None:
        for name in AGREEMENT_FIELDS:
            rv = rules.fields.get(name)
            if rv is None or rules.field_basis.get(name) != "explicit":
                continue
            mv = fields.get(name)
            if mv is not None and not values_equal(mv, rv, name, ctry or ""):
                res.reasons.append(f"{CONTRADICTS_RULES}:{name}")
            elif mv is None and not candidate.adr_lines:
                res.reasons.append(f"{CONTRADICTS_RULES}:{name}")
        if rules.fields.get("Ctry") and ctry and rules.fields["Ctry"] != ctry and rules.field_basis.get("Ctry") != "elimination":
            res.reasons.append(f"{CONTRADICTS_RULES}:Ctry")

    # consistency: a written town exists in the gazetteer for that country
    town = fields.get("TwnNm")
    if town is not None and ctry is not None:
        if not gazetteer_loaded(gazetteer):
            res.unchecked = True
        elif not town_in_gazetteer(town, ctry, gazetteer, profiles.get(ctry)):
            res.reasons.append(TOWN_NOT_IN_GAZETTEER)
    return res
