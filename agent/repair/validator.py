"""Deterministic validator. Pure functions over a candidate address; no I/O at call time, no LLM.

validate(candidate) returns reason codes (empty list = valid):
  ADDR_UNSTRUCTURED, MISSING_TWNNM, MISSING_CTRY, INVALID_CTRY, FIELD_TOO_LONG, POSTCODE_FORMAT,
  HYBRID_LINES_EXCEEDED, HYBRID_DUPLICATION

Nothing is special-cased for records with no town: when no town is written, TwnNm is absent, the validator says
MISSING_TWNNM, and the pipeline routes the address to REVIEW.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from agent.repair.iso3166 import ALPHA2
from agent.rules.engine import load_config
from agent.rules.profile import all_profiles
from agent.rules.xsd import V1_FIELDS, load_schema

ADDR_UNSTRUCTURED = "ADDR_UNSTRUCTURED"
MISSING_TWNNM = "MISSING_TWNNM"
MISSING_CTRY = "MISSING_CTRY"
INVALID_CTRY = "INVALID_CTRY"
FIELD_TOO_LONG = "FIELD_TOO_LONG"
POSTCODE_FORMAT = "POSTCODE_FORMAT"
HYBRID_LINES_EXCEEDED = "HYBRID_LINES_EXCEEDED"
HYBRID_DUPLICATION = "HYBRID_DUPLICATION"


@dataclass
class Candidate:
    fields: dict[str, str] = field(default_factory=dict)   # structured elements, XSD names
    adr_lines: list[str] = field(default_factory=list)     # hybrid: unstructured AdrLine entries

    @classmethod
    def from_dict(cls, d: dict) -> "Candidate":
        d = dict(d)
        lines = [str(x) for x in d.pop("AdrLine", None) or []]
        return cls({k: v for k, v in d.items() if isinstance(v, str) and v != ""}, lines)

    def as_dict(self) -> dict:
        out = dict(self.fields)
        if self.adr_lines:
            out["AdrLine"] = list(self.adr_lines)
        return out


def max_adr_lines() -> int:
    """The AdrLine maximum is the existing config value (agent/rules/config.yaml). It is a placeholder:
    the real CBPR+ limit for hybrid addresses must be confirmed (docs/decisions/hybrid-address.md)."""
    return int(load_config()["max_adr_lines"])


def validate(candidate: Candidate, max_lines: int | None = None) -> list[str]:
    schema = load_schema()
    reasons: list[str] = []
    fields = candidate.fields
    lines = candidate.adr_lines

    if not fields and not lines:
        return [ADDR_UNSTRUCTURED]
    if not any(k in fields for k in V1_FIELDS):
        reasons.append(ADDR_UNSTRUCTURED)
    if "TwnNm" not in fields:
        reasons.append(MISSING_TWNNM)
    ctry = fields.get("Ctry")
    if ctry is None:
        reasons.append(MISSING_CTRY)
    elif ctry not in ALPHA2:
        reasons.append(INVALID_CTRY)

    too_long = False
    for name, value in fields.items():
        spec = schema.elements.get(name)
        if spec is not None and spec.max_length is not None and len(value) > spec.max_length:
            too_long = True
    adr_max = schema.max_length("AdrLine")
    if any(len(l) > adr_max for l in lines):
        too_long = True
    if too_long:
        reasons.append(FIELD_TOO_LONG)

    pc = fields.get("PstCd")
    if pc is not None and ctry in all_profiles():
        prof = all_profiles()[ctry]
        patterns = prof.postcode_patterns + prof.partial_patterns
        if patterns and not any(p.fullmatch(pc.strip()) for p in patterns):
            reasons.append(POSTCODE_FORMAT)

    limit = max_lines if max_lines is not None else max_adr_lines()
    if lines:
        if len(lines) > limit:
            reasons.append(HYBRID_LINES_EXCEEDED)
        joined = " ".join(l.casefold() for l in lines)
        for name, value in fields.items():
            if name != "Ctry" and value.casefold() in joined:
                reasons.append(HYBRID_DUPLICATION)
                break
    return reasons
