"""Small statistics helpers, standard library only."""
from __future__ import annotations

import math

MIN_BUCKET = 5  # a bucket with fewer records than this prints only its count, never a percentage


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float] | None:
    """Wilson 95% score interval for k successes in n trials. None when n is 0."""
    if n <= 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    low, high = max(0.0, centre - half), min(1.0, centre + half)
    return (0.0 if k == 0 else low), (1.0 if k == n else high)


def percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile (q in 0..100). 0.0 for an empty list."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(q / 100 * len(ordered)))
    return ordered[rank - 1]


def rate(k: int, n: int) -> dict:
    """{'k', 'n', 'rate', 'ci'}. rate and ci are None when n is under MIN_BUCKET (the count alone is reported)."""
    out = {"k": k, "n": n, "rate": None, "ci": None}
    if n >= MIN_BUCKET:
        out["rate"] = k / n
        out["ci"] = wilson(k, n)
    return out


def fmt(r: dict, ci: bool = False) -> str:
    """'87.5% (14/16)'; 'k/n' alone for a small bucket; '-' for n = 0."""
    k, n = r["k"], r["n"]
    if n == 0:
        return "- (0/0)"
    if r["rate"] is None:
        return f"{k}/{n}"
    text = f"{100 * r['rate']:.1f}% ({k}/{n})"
    if ci and r["ci"]:
        text += f" [{100 * r['ci'][0]:.1f}-{100 * r['ci'][1]:.1f}]"
    return text
