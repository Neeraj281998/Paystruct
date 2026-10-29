from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pytest

from addrgen import countries
from addrgen.generate import generate

GENERATOR_DIR = Path(__file__).resolve().parents[1]
SEED = int((GENERATOR_DIR / "SEED").read_text().strip())


@pytest.fixture(scope="session")
def seed() -> int:
    return SEED


@pytest.fixture(scope="session")
def records(seed) -> list[dict]:
    """4,800 records: every country, all three tiers, from the project seed (200 per country and tier)."""
    return list(generate(seed, 4800, countries.codes()))


@pytest.fixture(scope="session")
def by_country(records) -> dict[str, list[dict]]:
    grouped = defaultdict(list)
    for rec in records:
        grouped[rec["country"]].append(rec)
    return grouped
