from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Part:
    """One written value. text is how it is (or will be) written, which is also its gold value.

    field is None for unlabelled text (an Indian landmark): it is written in the raw lines but is never in gold.
    comma_after asks the renderer to follow this part with a comma inside its line ("Austin, TX 78701"); it is
    dropped when commas are missing or the text already ends with a full stop.
    """

    field: str | None
    text: str
    comma_after: bool = False


@dataclass
class TownBlock:
    """Locality, town plus postcode (and region), and county lines of an address, as segments."""

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
