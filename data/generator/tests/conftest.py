from __future__ import annotations

from pathlib import Path

import pytest

from addrgen.generate import generate

GENERATOR_DIR = Path(__file__).resolve().parents[1]
SEED = int((GENERATOR_DIR / "SEED").read_text().strip())


@pytest.fixture(scope="session")
def seed() -> int:
    return SEED


@pytest.fixture(scope="session")
def records(seed) -> list[dict]:
    """1,800 records: IE and GB, all three tiers, from the project seed."""
    return list(generate(seed, 1800, ["IE", "GB"]))
