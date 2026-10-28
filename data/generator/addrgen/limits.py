"""Element names, order and maximum lengths of the postal address, read from the XSD.

The XSD is the source of truth (docs/decisions/xsd-versions.md records what it says). Nothing here is hard-coded
from the spec's Address elements table, which was written for PostalAddress24 and is wrong for PostalAddress27.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
XSD_DIR = REPO_ROOT / "service" / "src" / "main" / "resources" / "xsd"
PACS008_XSD = XSD_DIR / "pacs.008.001.14.xsd"
PAIN001_XSD = XSD_DIR / "pain.001.001.13.xsd"

_XS = "{http://www.w3.org/2001/XMLSchema}"


@dataclass(frozen=True)
class ElementLimit:
    name: str
    max_length: int | None  # None when the XSD gives no maxLength (pattern-restricted codes, complex types)
    pattern: str | None
    max_occurs: int | None  # None means unbounded
    complex: bool


def load_limits(xsd_path: Path = PACS008_XSD) -> dict[str, ElementLimit]:
    """The children of the postal address type, in XSD sequence order."""
    root = ET.parse(xsd_path).getroot()
    complex_types = {e.get("name"): e for e in root.findall(f"{_XS}complexType")}
    simple_types = {e.get("name"): e for e in root.findall(f"{_XS}simpleType")}

    type_name = next(
        e.get("type")
        for e in root.iter(f"{_XS}element")
        if e.get("name") == "PstlAdr" and (e.get("type") or "").startswith("PostalAddress")
    )
    sequence = complex_types[type_name].find(f"{_XS}sequence")
    limits: dict[str, ElementLimit] = {}
    for el in sequence.findall(f"{_XS}element"):
        type_ref = el.get("type")
        max_length = pattern = None
        simple = simple_types.get(type_ref)
        if simple is not None:
            restriction = simple.find(f"{_XS}restriction")
            for facet in restriction:
                if facet.tag == f"{_XS}maxLength":
                    max_length = int(facet.get("value"))
                elif facet.tag == f"{_XS}pattern":
                    pattern = facet.get("value")
        max_occurs = el.get("maxOccurs", "1")
        limits[el.get("name")] = ElementLimit(
            name=el.get("name"),
            max_length=max_length,
            pattern=pattern,
            max_occurs=None if max_occurs == "unbounded" else int(max_occurs),
            complex=type_ref in complex_types,
        )
    return limits


LIMITS = load_limits()

# Raw lines: the AdrLine limit from the XSD.
MAX_LINE_LENGTH = LIMITS["AdrLine"].max_length
MAX_LINES = LIMITS["AdrLine"].max_occurs

# The fields the labelling guide uses in v1, in XSD order. Dept, SubDept, UnitNb, DstrctNm and CareOf are not used.
GOLD_FIELDS = tuple(
    name
    for name in LIMITS
    if name in {"StrtNm", "BldgNb", "BldgNm", "Flr", "Room", "PstBx", "PstCd", "TwnNm", "TwnLctnNm", "CtrySubDvsn", "Ctry"}
)
