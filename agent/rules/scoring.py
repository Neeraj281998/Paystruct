"""The scorer of labelling guide section 10, exactly.

A predicted field equals the gold field when, for both: Unicode NFC, case-folded, runs of whitespace collapsed to one
space, leading and trailing whitespace and the punctuation `, . ;` trimmed. For PstCd only, all whitespace is removed.
Allowlisted abbreviation pairs are equal. Exact match: every gold field matches and no extra field is predicted.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from agent.rules import allowlist
from agent.rules.xsd import V1_FIELDS

_WS = re.compile(r"\s+")
_TRIM = " \t\r\n,.;"


def normalise(value: str, name: str) -> str:
    v = unicodedata.normalize("NFC", value).casefold()
    v = _WS.sub(" ", v).strip(_TRIM)
    if name == "PstCd":
        v = _WS.sub("", v)
    return v


def values_equal(pred: str, gold: str, name: str, country: str) -> bool:
    p, g = normalise(pred, name), normalise(gold, name)
    if p == g:
        return True
    if name in ("PstCd", "Ctry"):
        return False
    return allowlist.equivalent(p, g, country)


@dataclass
class RecordScore:
    exact: bool
    matched: list[str] = field(default_factory=list)
    wrong: list[str] = field(default_factory=list)      # predicted, different from gold
    missing: list[str] = field(default_factory=list)    # in gold, not predicted
    extra: list[str] = field(default_factory=list)      # predicted, not in gold
    n_gold: int = 0

    def pattern(self) -> str:
        parts = [f"{f}:wrong" for f in self.wrong] + [f"{f}:missing" for f in self.missing] + [f"{f}:extra" for f in self.extra]
        return "+".join(sorted(parts)) or "exact"


def score_record(pred: dict[str, str], gold: dict[str, str], country: str) -> RecordScore:
    pred = {k: v for k, v in pred.items() if k in V1_FIELDS and v is not None and v != ""}
    s = RecordScore(exact=False, n_gold=len(gold))
    for name, gv in gold.items():
        if name not in pred:
            s.missing.append(name)
        elif values_equal(pred[name], gv, name, country):
            s.matched.append(name)
        else:
            s.wrong.append(name)
    s.extra = [n for n in pred if n not in gold]
    s.exact = not (s.missing or s.wrong or s.extra)
    return s
