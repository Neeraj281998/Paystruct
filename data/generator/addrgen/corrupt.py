"""Corruption functions. Each returns True only if it actually changed the address, so a tag is never added for a
corruption that did nothing. Text-level functions change Part.text (and so the gold, which keeps the text as written);
layout-level functions move parts between lines and never change a value.
"""
from __future__ import annotations

import random

from addrgen.limits import LIMITS
from addrgen.model import Part

_KEYBOARD_NEIGHBOURS = {
    "a": "qwsz", "b": "vghn", "c": "xdfv", "d": "serfcx", "e": "wsdr", "f": "drtgvc", "g": "ftyhbv", "h": "gyujnb",
    "i": "ujko", "j": "huikmn", "k": "jiolm", "l": "kop", "m": "njk", "n": "bhjm", "o": "iklp", "p": "ol",
    "q": "wa", "r": "edft", "s": "awedxz", "t": "rfgy", "u": "yhji", "v": "cfgb", "w": "qase", "x": "zsdc",
    "y": "tghu", "z": "asx",
}


# ---- text-level ------------------------------------------------------------------------------------------------
def abbreviate(parts: list[Part], rng: random.Random, module) -> bool:
    """Street and room words written abbreviated, using the country's own table (guide: one list per country)."""
    changed = False
    for part in parts:
        if part.field == "StrtNm":
            new = module.abbreviate_street(part.text, rng)
        elif part.field == "Room":
            new = module.abbreviate_room(part.text, rng)
        else:
            continue
        if new != part.text:
            part.text = new
            changed = True
    return changed


def typo(parts: list[Part], rng: random.Random, module) -> bool:
    """One typo in one word of a street or building name: never the first letter, never the street or building word,
    never a town, postcode, number or country. The country says where a typo may go."""
    candidates = []
    for part in parts:
        if part.field in ("StrtNm", "BldgNm"):
            for span in module.typo_spans(part.field, part.text):
                candidates.append((part, span))
    if not candidates:
        return False
    part, (start, end) = rng.choice(candidates)
    word = part.text[start:end]
    for _ in range(10):
        broken = _break(word, rng)
        if broken != word:
            candidate = part.text[:start] + broken + part.text[end:]
            if len(candidate) <= LIMITS[part.field].max_length:
                part.text = candidate
                return True
    return False


def _break(word: str, rng: random.Random) -> str:
    pos = rng.randrange(1, len(word) - 1)  # never the first letter
    op = rng.choice(("delete", "duplicate", "swap", "substitute"))
    if op == "delete":
        return word[:pos] + word[pos + 1:]
    if op == "duplicate":
        return word[:pos] + word[pos] + word[pos:]
    if op == "swap":
        return word[:pos] + word[pos + 1] + word[pos] + word[pos + 2:]
    neighbours = _KEYBOARD_NEIGHBOURS.get(word[pos].lower(), "")
    if not neighbours:
        return word
    new = rng.choice(neighbours)
    return word[:pos] + (new.upper() if word[pos].isupper() else new) + word[pos + 1:]


def postcode_no_space(parts: list[Part]) -> bool:
    for part in parts:
        if part.field == "PstCd" and " " in part.text:
            part.text = part.text.replace(" ", "")
            return True
    return False


def all_caps(parts: list[Part]) -> bool:
    changed = False
    for part in parts:
        upper = part.text.upper()
        changed |= upper != part.text
        part.text = upper
    return changed


# ---- layout-level (segments are the logical lines; no value changes) --------------------------------------------
def _find(segments: list[list[Part]], field: str) -> tuple[int, int] | None:
    for si, seg in enumerate(segments):
        for pi, part in enumerate(seg):
            if part.field == field:
                return si, pi
    return None


def _signature(segments: list[list[Part]]) -> list[list[tuple[str, str]]]:
    return [[(p.field, p.text) for p in seg] for seg in segments]


def reorder(segments: list[list[Part]], rng: random.Random) -> bool:
    """Postcode before town, two street-side lines swapped, or the town line first."""
    before = _signature(segments)
    town_at = next((i for i, seg in enumerate(segments) if any(p.field == "TwnNm" for p in seg)), None)
    options = []
    if town_at is not None:
        seg = segments[town_at]
        if any(p.field == "TwnNm" for p in seg) and any(p.field == "PstCd" for p in seg):
            options.append("postcode_first")
        if town_at >= 2:
            options.append("swap_street_lines")
        if town_at >= 1:
            options.append("town_first")
    if not options:
        return False
    choice = rng.choice(options)
    if choice == "postcode_first":
        segments[town_at].reverse()
    elif choice == "swap_street_lines":
        i = rng.randrange(0, town_at - 1)
        segments[i], segments[i + 1] = segments[i + 1], segments[i]
    else:
        segments.insert(0, segments.pop(town_at))
    return _signature(segments) != before


def postcode_wrong_line(segments: list[list[Part]], rng: random.Random) -> bool:
    """The postcode moves off its line: onto the end of the first line, or onto a line of its own at the end."""
    found = _find(segments, "PstCd")
    if found is None:
        return False
    before = _signature(segments)
    si, pi = found
    part = segments[si].pop(pi)
    if not segments[si]:
        segments.pop(si)
    if segments and rng.random() < 0.5:
        segments[0].append(part)
    else:
        segments.append([part])
    if _signature(segments) == before:  # it was alone on the last line already: put it on the first line instead
        segments.pop()
        segments[0].append(part)
    return _signature(segments) != before


def postcode_split(segments: list[list[Part]], rng: random.Random, halves: tuple[str, str] | None) -> bool:
    """The postcode's two halves are on neighbouring lines. Gold keeps the whole postcode.

    A postcode that ends its line ("Galway H91 | AB12") has its first half stay and its second half start the next
    line. A postcode that starts its line ("1015 | CJ Amsterdam", postcode before town) has its first half end the
    previous line and its second half stay. A postcode in the middle of a line is left alone."""
    found = _find(segments, "PstCd")
    if found is None or halves is None:
        return False
    si, pi = found
    first, second = Part("PstCd", halves[0]), Part("PstCd", halves[1])
    if pi == len(segments[si]) - 1:
        segments[si][pi] = first
        if si + 1 < len(segments):
            segments[si + 1].insert(0, second)
        else:
            segments.append([second])
        return True
    if pi == 0:
        segments[si][pi] = second
        if si > 0:
            segments[si - 1].append(first)
        else:
            segments.insert(0, [first])
        return True
    return False
