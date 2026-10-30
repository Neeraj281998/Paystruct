"""Element names and limits of PostalAddress27, read from the supplied XSD (docs/decisions/xsd-versions.md)."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
XSD_PATH = REPO_ROOT / "service/src/main/resources/xsd/pacs.008.001.14.xsd"
_XS = "{http://www.w3.org/2001/XMLSchema}"

# Elements the rules engine may fill in v1 (labelling guide, "Fields used in v1").
V1_FIELDS = ("StrtNm", "BldgNb", "BldgNm", "Flr", "Room", "PstBx", "PstCd", "TwnNm", "TwnLctnNm", "CtrySubDvsn", "Ctry")


@dataclass(frozen=True)
class ElementSpec:
    name: str
    max_length: int | None
    max_occurs: int
    pattern: str | None


class PostalAddressSchema:
    def __init__(self, elements: dict[str, ElementSpec]):
        self.elements = elements

    def max_length(self, name: str) -> int | None:
        return self.elements[name].max_length

    def max_occurs(self, name: str) -> int:
        return self.elements[name].max_occurs

    def order(self) -> list[str]:
        return list(self.elements)


def _simple_type_limits(root: ET.Element, type_name: str) -> tuple[int | None, str | None]:
    for st in root.iter(f"{_XS}simpleType"):
        if st.get("name") == type_name:
            restriction = st.find(f"{_XS}restriction")
            if restriction is None:
                return None, None
            max_len = restriction.find(f"{_XS}maxLength")
            pattern = restriction.find(f"{_XS}pattern")
            return (int(max_len.get("value")) if max_len is not None else None,
                    pattern.get("value") if pattern is not None else None)
    return None, None


@lru_cache(maxsize=4)
def load_schema(path: Path = XSD_PATH) -> PostalAddressSchema:
    root = ET.parse(path).getroot()
    for ct in root.iter(f"{_XS}complexType"):
        if ct.get("name") == "PostalAddress27":
            elements: dict[str, ElementSpec] = {}
            for el in ct.iter(f"{_XS}element"):
                type_name = re.sub(r"^.*:", "", el.get("type", ""))
                max_len, pattern = _simple_type_limits(root, type_name)
                occurs = el.get("maxOccurs", "1")
                elements[el.get("name")] = ElementSpec(el.get("name"), max_len, 10**6 if occurs == "unbounded" else int(occurs), pattern)
            return PostalAddressSchema(elements)
    raise ValueError(f"PostalAddress27 not found in {path}")
