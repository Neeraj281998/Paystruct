"""Postcode-to-town ties derived from GeoNames (scripts/build_postcode_ties.py), loaded once.

Source: GeoNames postal code data, CC BY 4.0, https://www.geonames.org. The JSON is committed; the GeoNames files are not.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_PATH = Path(__file__).parent / "data" / "postcode_ties.json"


@lru_cache(maxsize=None)
def ties() -> dict:
    return json.loads(_PATH.read_text(encoding="utf-8"))
