"""Metrics for one run. Scoring is agent.rules.scoring (labelling guide section 10), used as it is, never reimplemented."""
from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass

from agent.rules import allowlist
from agent.rules.scoring import RecordScore, score_record
from agent.rules.xsd import V1_FIELDS
from evals.stats import percentile, rate

ROUTES = ("ACCEPT", "NEEDS_LLM", "REVIEW")
_EDGE = ",.;:()[]\"'`"


@dataclass
class RecordEval:
    rec: dict
    fields: dict[str, str]
    route: str
    latency_s: float
    cost_usd: float
    score: RecordScore
    hallucinated: list[str]  # element names whose value is not built from the input

    @property
    def accepted(self) -> bool:
        return self.route == "ACCEPT"


def _words(text: str) -> list[str]:
    out = []
    for w in unicodedata.normalize("NFC", text).casefold().split():
        w = w.strip(_EDGE)
        if w:
            out.append(w)
    return out


def hallucinated_fields(fields: dict[str, str], raw_lines: list[str], country: str) -> list[str]:
    """Elements whose value is not built from tokens in the input.

    Exempt: Ctry (the one value allowed to be added) and allowlisted expansions ('St' -> 'Street').
    A value is built from the input when every word of it is an input word, or the expansion of one.
    """
    in_words = {w for line in raw_lines for w in _words(line)}
    in_canon = {allowlist.canonical(w, country) for w in in_words}
    bad = []
    for name, value in fields.items():
        if name == "Ctry" or name not in V1_FIELDS:
            continue
        for w in _words(value):
            if w not in in_words and allowlist.canonical(w, country) not in in_canon:
                bad.append(name)
                break
    return bad


def evaluate_record(rec: dict, out) -> RecordEval:
    fields = {k: v for k, v in out.fields.items() if k in V1_FIELDS and v}
    sc = score_record(fields, rec["gold"], rec["country"])
    return RecordEval(rec, fields, out.route, out.latency_s, out.cost_usd, sc, hallucinated_fields(fields, rec["raw_lines"], rec["country"]))


def _element_prf(evals: list[RecordEval]) -> dict:
    stats = {f: Counter() for f in V1_FIELDS}
    for e in evals:
        s = e.score
        for f in s.matched:
            stats[f]["tp"] += 1
        for f in s.wrong:
            stats[f]["fp"] += 1
            stats[f]["fn"] += 1
        for f in s.missing:
            stats[f]["fn"] += 1
        for f in s.extra:
            stats[f]["fp"] += 1
    out = {}
    for f, c in stats.items():
        tp, fp, fn = c["tp"], c["fp"], c["fn"]
        n_gold = tp + fn
        p = tp / (tp + fp) if tp + fp else None
        r = tp / (tp + fn) if tp + fn else None
        f1 = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
        out[f] = {"tp": tp, "fp": fp, "fn": fn, "n_gold": n_gold, "precision": p, "recall": r, "f1": f1}
    return out


def headline(evals: list[RecordEval]) -> dict:
    """The rates shared by the whole run and by every breakdown bucket."""
    n = len(evals)
    accepted = [e for e in evals if e.accepted]
    exact = sum(e.score.exact for e in evals)
    return {
        "n": n,
        "exact_all": rate(exact, n),
        "auto_correct": rate(sum(e.accepted and e.score.exact for e in evals), n),
        "false_repair": rate(sum(not e.score.exact for e in accepted), len(accepted)),
        "hallucinated_records": rate(sum(bool(e.hallucinated) for e in evals), n),
        "routes": {r: rate(sum(e.route == r for e in evals), n) for r in ROUTES},
    }


def breakdown(evals: list[RecordEval], keys) -> dict:
    groups: dict[str, list[RecordEval]] = defaultdict(list)
    for e in evals:
        for k in keys(e):
            groups[k].append(e)
    return {k: headline(v) for k, v in sorted(groups.items())}


def compute(evals: list[RecordEval]) -> dict:
    n = len(evals)
    h = headline(evals)
    matched = sum(len(e.score.matched) for e in evals)
    gold_fields = sum(e.score.n_gold for e in evals)
    no_town = [e for e in evals if "TwnNm" not in e.rec["gold"]]
    patterns = Counter(e.score.pattern() for e in evals if not e.score.exact)
    lat = [e.latency_s * 1000 for e in evals]
    m = {
        **h,
        "field_accuracy": rate(matched, gold_fields),
        "per_element": _element_prf(evals),
        "not_repaired": rate(sum(not e.accepted for e in evals), n),  # rules-only: every non-ACCEPT record
        "hallucinated_values": sum(len(e.hallucinated) for e in evals),
        "hallucinated_by_element": dict(Counter(f for e in evals for f in e.hallucinated)),
        "no_town": {"n": len(no_town),
                    "output_a_town": sum("TwnNm" in e.fields for e in no_town),
                    "hallucinated_town": sum("TwnNm" in e.hallucinated for e in no_town),
                    "accepted_with_a_town": sum(e.accepted and "TwnNm" in e.fields for e in no_town)},
        "latency_ms": {"p50": round(percentile(lat, 50), 3), "p95": round(percentile(lat, 95), 3)},
        "cost_usd_total": round(sum(e.cost_usd for e in evals), 6),
        "cost_per_1000_usd": round(1000 * sum(e.cost_usd for e in evals) / n, 6) if n else 0.0,
        "failure_patterns": dict(patterns.most_common()),  # counts by pattern; no record ids
        "by_country": breakdown(evals, lambda e: [e.rec["country"]]),
        "by_tier": breakdown(evals, lambda e: [e.rec.get("difficulty", "?")]),
        "by_tag": breakdown(evals, lambda e: e.rec.get("tags") or ["untagged"]),
    }
    return m
