"""Completeness: a repair may not lose text.

Every token of the input must appear in a field or in AdrLine of the candidate, except
  * the country text (the ISO code or a country name of the candidate's own country),
  * separators and punctuation (the tokenizer removes them),
  * landmark phrases that the rules already recognise as landmarks (labelling guide section 18).
Anything else that is missing is lost text: the hard reason DROPS_TEXT, so the result goes back to the model and then to REVIEW.
It applies to the rules' output and the model's output alike.
"""
from __future__ import annotations

import re
from collections import Counter

from agent.repair.validator import Candidate
from agent.rules import allowlist
from agent.rules.gazetteer import fold
from agent.rules.profile import Profile, all_profiles
from agent.rules.state import Token, tokenize

DROPS_TEXT = "DROPS_TEXT"
_EDGE = ",.;:()[]\"'`"
_PIECES = re.compile(r"[-/]")


def _clean(word: str) -> str:
    return word.strip(_EDGE)


def _country_tokens(tokens: list[Token], code: str | None, profile: Profile | None, all_lower: bool) -> set[int]:
    if not code or profile is None:
        return set()
    out = {t.idx for t in tokens if t.text == code or (all_lower and t.text.upper() == code)}
    names = {fold(n) for n in profile.names}
    for n in range(1, 5):
        for i in range(len(tokens) - n + 1):
            if fold(" ".join(t.text for t in tokens[i:i + n])) in names:
                out |= {t.idx for t in tokens[i:i + n]}
    return out


def _landmark_tokens(tokens: list[Token], rules) -> set[int]:
    if rules is None:
        return set()
    spans = [(l.start, l.end) for l in rules.leftovers if l.reason.startswith("landmark")]
    return {t.idx for t in tokens if any(t.start >= s and t.end <= e for s, e in spans)}


def check(candidate: Candidate, raw_lines: list[str], rules=None, profiles: dict[str, Profile] | None = None) -> list[str]:
    """The pieces of input text that the candidate loses (empty list: nothing is lost)."""
    profiles = profiles or all_profiles()
    _, tokens = tokenize(raw_lines)
    code = candidate.fields.get("Ctry")
    country = code if code in profiles else ""
    all_lower = not any(c.isupper() for line in raw_lines for c in line)
    exempt = _country_tokens(tokens, code, profiles.get(code or ""), all_lower) | _landmark_tokens(tokens, rules)

    values = [v for k, v in candidate.fields.items() if k != "Ctry"] + list(candidate.adr_lines)
    words: Counter[str] = Counter()
    pieces: Counter[str] = Counter()
    for v in values:
        for w in v.split():
            w = _clean(w)
            if not w:
                continue
            words[allowlist.canonical(w, country)] += 1
            for p in _PIECES.split(w):
                if p:
                    pieces[allowlist.canonical(p, country)] += 1
    postcode = re.sub(r"\s+", "", candidate.fields.get("PstCd", "")).casefold()

    lost: list[Token] = []
    for t in tokens:
        if t.idx in exempt:
            continue
        w = _clean(t.text)
        if not w:
            continue
        c = allowlist.canonical(w, country)
        if words[c] > 0:
            words[c] -= 1
            continue
        parts = [allowlist.canonical(p, country) for p in _PIECES.split(w) if p]
        if len(parts) > 1 and all(pieces[p] > 0 for p in parts):
            continue                                   # "5-123" written as Room "5" and BldgNb "123"
        if len(c) >= 2 and postcode and c in postcode:
            continue                                   # a postcode written in two pieces and kept in one
        lost.append(t)
    phrases: list[list[Token]] = []
    for t in lost:
        if phrases and t.idx == phrases[-1][-1].idx + 1:
            phrases[-1].append(t)
        else:
            phrases.append([t])
    return [" ".join(x.text for x in p) for p in phrases]
