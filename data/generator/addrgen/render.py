"""Turns a ground-truth address into messy raw lines and its gold, applying the chosen corruptions."""
from __future__ import annotations

import random
from dataclasses import replace

from addrgen import corrupt
from addrgen.countries.base import CountryModule
from addrgen.limits import GOLD_FIELDS, MAX_LINE_LENGTH, MAX_LINES
from addrgen.model import Part, Rendered, Truth

CORRUPTIONS = (
    "all_caps", "extra_spaces", "one_line", "missing_commas", "reordered", "postcode_split", "postcode_no_space",
    "postcode_wrong_line", "typo", "abbreviated", "country_name", "no_country",
)


class RenderError(Exception):
    """This truth and these corruptions cannot make a valid record; the generator tries another."""


def render(truth: Truth, ops: set[str], module: CountryModule, rng: random.Random) -> Rendered:
    segments = [[replace(p) for p in seg] for seg in truth.segments]  # copies, keeping comma_after
    tags = set(truth.tags)

    # Country: absent, a name, or the ISO code. It is not part of the truth segments; it is the last line.
    country_part = None
    if "no_country" in ops:
        tags.add("no_country")
    else:
        if "country_name" in ops:
            country_part = Part("Ctry", rng.choice(module.country_names))
            tags.add("country_name")
        else:
            country_part = Part("Ctry", module.code)

    # Text-level corruptions change the written value, and so the gold.
    parts = [p for seg in segments for p in seg] + ([country_part] if country_part else [])
    if "abbreviated" in ops and corrupt.abbreviate(parts, rng, module):
        tags.add("abbreviated")
    if "typo" in ops and corrupt.typo(parts, rng, module):
        tags.add("typo")
    if "postcode_no_space" in ops and module.can_drop_postcode_space and corrupt.postcode_no_space(parts):
        tags.add("postcode_no_space")
    if "all_caps" in ops and corrupt.all_caps(parts):
        tags.add("all_caps")

    gold: dict[str, str] = {}
    for seg in segments:
        for part in seg:
            if part.field is None:  # unlabelled text (an Indian landmark) is written but never in gold
                continue
            if part.field in gold:
                raise RenderError(f"duplicate field {part.field}")
            gold[part.field] = part.text
    gold["Ctry"] = module.code  # the one gold value that need not appear in the text
    gold = {name: gold[name] for name in GOLD_FIELDS if name in gold}  # XSD order

    if country_part:
        segments.append([country_part])

    # Layout-level corruptions move values between lines.
    if "reordered" in ops and corrupt.reorder(segments, rng):
        tags.add("reordered")
    if "postcode_wrong_line" in ops and corrupt.postcode_wrong_line(segments, rng):
        tags.add("postcode_wrong_line")
    if "postcode_split" in ops:
        pc = next((p.text for seg in segments for p in seg if p.field == "PstCd"), None)
        if corrupt.postcode_split(segments, rng, module.split_postcode(pc) if pc else None):
            tags.add("postcode_split")

    lines = [[seg] for seg in segments]
    postcode_moved = {"postcode_wrong_line", "postcode_split"} & tags
    # Natural variation (not a corruption): town, postcode and country often share the last line.
    if country_part and len(lines) >= 3 and not postcode_moved and rng.random() < 0.4:
        lines[-2].extend(lines.pop())
    if "one_line" in ops and len(lines) > 1:
        lines = [[seg for line in lines for seg in line]]
        tags.add("one_line")

    raw_lines, extra_applied, comma_sites = _format(lines, rng, extra="extra_spaces" in ops,
                                                    commas="missing_commas" not in ops)
    if "missing_commas" in ops and comma_sites > 0:  # only a corruption if there was a comma to leave out
        tags.add("missing_commas")

    wrapped: list[str] = []
    for line in raw_lines:
        pieces = _wrap(line)
        if len(pieces) > 1:
            tags.add("long_line_split")
        wrapped.extend(pieces)
    if len(wrapped) > MAX_LINES:
        raise RenderError("too many lines")
    # Wrapping strips the spaces at a break, so judge extra_spaces by the lines as they finally are.
    if "extra_spaces" in ops and extra_applied and any(line != line.strip() or "  " in line for line in wrapped):
        tags.add("extra_spaces")

    return Rendered(wrapped, gold, tags, module.code if "no_country" in ops else None)


def _format(lines, rng, extra: bool, commas: bool) -> tuple[list[str], bool, int]:
    """Join parts and segments into strings. Returns the lines, whether an extra space was added, and how many places
    a comma could go (so a missing_commas request that had nowhere to put one is not tagged)."""
    trailing = rng.random() < 0.5  # multi-line style: commas at line ends (natural variation)
    extra_applied = False
    comma_sites = 0
    out = []
    for li, line in enumerate(lines):
        text = ""
        for si, segment in enumerate(line):
            # Extra spaces only ever go between values, never inside one, so gold keeps single spaces.
            seg_text = segment[0].text
            for prev, part in zip(segment, segment[1:]):
                can_comma = prev.comma_after and not seg_text.endswith(".")
                comma_sites += can_comma
                double = extra and rng.random() < 0.5
                extra_applied |= double
                seg_text += ("," if commas and can_comma else "") + ("  " if double else " ") + part.text
            if si > 0:
                can_comma = not text.endswith(".")
                comma_sites += can_comma
                double = extra and rng.random() < 0.5
                extra_applied |= double
                text += ("," if commas and can_comma else "") + ("  " if double else " ") + seg_text
            else:
                text = seg_text
        if li < len(lines) - 1 and trailing and not text.endswith("."):
            comma_sites += 1
            text += "," if commas else ""
        out.append(text)
    if extra:
        for i in range(len(out)):
            lead, trail = rng.random() < 0.15, rng.random() < 0.25
            out[i] = (" " if lead else "") + out[i] + (" " if trail else "")
            extra_applied |= lead or trail
        if not extra_applied:
            out[0] += " "
            extra_applied = True
    return out, extra_applied, comma_sites


def _wrap(line: str, width: int = MAX_LINE_LENGTH) -> list[str]:
    """Split a line longer than width at word boundaries. Gold is untouched, so a value may end up across two lines."""
    pieces = []
    while len(line) > width:
        cut = line.rfind(" ", 0, width + 1)
        if cut <= 0 or not line[:cut].strip():
            raise RenderError("cannot wrap line")
        pieces.append(line[:cut].rstrip())
        line = line[cut + 1:].lstrip()
    pieces.append(line)
    return pieces
