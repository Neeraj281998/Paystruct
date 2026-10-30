"""Rule base class, the shared context, and small helpers over tokens."""
from __future__ import annotations

import re
from dataclasses import dataclass

from agent.rules.gazetteer import Gazetteer
from agent.rules.profile import Profile
from agent.rules.state import ParseState, SEP_COMMA, Token
from agent.rules.xsd import PostalAddressSchema


@dataclass
class RuleContext:
    profiles: dict[str, Profile]
    gazetteer: Gazetteer
    schema: PostalAddressSchema
    config: dict


class Rule:
    """A small step: apply(state) -> new state. The input state is never changed."""
    id = "rule"

    def __init__(self, ctx: RuleContext):
        self.ctx = ctx

    def apply(self, state: ParseState) -> ParseState:
        new = state.copy()
        self.run(new)
        return new

    def run(self, state: ParseState) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    def profile(self, state: ParseState) -> Profile | None:
        return self.ctx.profiles.get(state.country) if state.country else None


def window_text(state: ParseState, idxs: list[int], join: str = " ") -> str:
    return join.join(state.tokens[i].text for i in idxs)


def free_windows(state: ParseState, max_tokens: int, max_inner_sep: int = 0):
    """Yield index lists of consecutive free tokens. Inside a window no separator stronger than `max_inner_sep`."""
    n = len(state.tokens)
    for i in range(n):
        if not state.is_free(i):
            continue
        window = [i]
        yield list(window)
        j = i
        while len(window) < max_tokens and j + 1 < n and state.is_free(j + 1) and state.tokens[j].sep <= max_inner_sep:
            j += 1
            window.append(j)
            yield list(window)


def fullmatch_any(patterns: list[re.Pattern], text: str) -> bool:
    return any(p.fullmatch(text) for p in patterns)


def is_number(profile: Profile, tok: Token) -> bool:
    return bool(profile.number_re.fullmatch(tok.text))


def has_digit(tok: Token) -> bool:
    return any(c.isdigit() for c in tok.text)


def street_word_sets(profile: Profile) -> set[str]:
    return profile.street_words_after | profile.street_words_before


def is_street_word(profile: Profile, tok: Token) -> bool:
    if tok.fold in street_word_sets(profile):
        return True
    return any(len(tok.fold) > len(s) and tok.fold.endswith(s) for s in profile.street_suffixes) or tok.fold in profile.street_suffixes


def building_word_hit(profile: Profile, folds: list[str]) -> bool:
    joined = " " + " ".join(folds) + " "
    return any(f" {w} " in joined for w in profile.building_words)


def token_gap(i: int, j: int, ref: int) -> int:
    """Number of tokens strictly between the span [i, j] and token `ref` (0 when adjacent)."""
    if ref < i:
        return i - ref - 1
    if ref > j:
        return ref - j - 1
    return 0


def country_name_keys(profiles) -> set[str]:
    """Folded country names and ISO codes of every profile ("Eire", "IE"): never a locality or a town."""
    from agent.rules.gazetteer import fold
    keys = set()
    for code, prof in profiles.items():
        keys.add(fold(code))
        keys |= {fold(n) for n in prof.names}
    return keys
