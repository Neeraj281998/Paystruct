from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Part:
    """One labelled value. text is how it is (or will be) written, which is also its gold value."""

    field: str
    text: str


@dataclass
class TownBlock:
    """Locality, town plus postcode, and county lines of an address, as segments."""

    segments: list[list[Part]]
    tags: set[str]


@dataclass
class Truth:
    """The correct structured address, before any mess. Segments are the logical lines, country excluded."""

    country: str
    template: str
    segments: list[list[Part]]
    tags: set[str]  # structure tags only


@dataclass
class Rendered:
    raw_lines: list[str]
    gold: dict[str, str]
    tags: set[str]  # structure tags plus the corruption tags that actually took effect
    country_hint: str | None
