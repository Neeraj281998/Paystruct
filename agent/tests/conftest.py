"""Test helpers: a small gazetteer (so tests do not need the GeoNames file) and a way to run chosen rules."""
from __future__ import annotations

import pytest

from agent.rules.engine import REGISTRY, RulesEngine, load_config
from agent.rules.gazetteer import Gazetteer, Place
from agent.rules.profile import all_profiles
from agent.rules.state import ParseState

PLACES = {
    "IE": [("Dublin", "07", 1024027), ("Cork", "04", 119230), ("Kilkenny", "01", 26512), ("Galway", "06", 79934), ("Bray", "13", 31872),
           ("Templeogue", "07", 14000), ("Sligo", "10", 19452)],
    "GB": [("London", "ENG", 7556900), ("Bristol", "ENG", 416400), ("Newcastle upon Tyne", "ENG", 148000), ("Gosforth", "ENG", 25000),
           ("Glasgow", "SCT", 591620), ("Belfast", "NIR", 280211), ("Street", "ENG", 12000), ("York", "ENG", 153717), ("Bath", "ENG", 94092)],
    "FR": [("Paris", "11", 2138551), ("Lyon", "84", 472317), ("Marseille", "93", 794811), ("Brest", "53", 139163), ("Metz", "44", 116429),
           ("Grenoble", "84", 158198), ("Dijon", "27", 156920)],
    "DE": [("Münster", "07", 310039), ("Köln", "07", 963395), ("Hamburg", "04", 1739117), ("Stuttgart", "01", 589793), ("Heidelberg", "01", 140000)],
    "NL": [("Eindhoven", "06", 209620), ("Utrecht", "09", 100000), ("Delft", "11", 98000), ("Amsterdam", "07", 741636)],
    "CA": [("Montréal", "10", 1600000), ("Halifax", "07", 390096), ("Victoria", "02", 92141), ("Québec", "10", 624177), ("Winnipeg", "03", 705244), ("Toronto", "08", 2600000), ("St. John's", "05", 100000)],
    "US": [("Atlanta", "GA", 463878), ("Austin", "TX", 790390), ("Pasadena", "CA", 138000), ("Washington", "DC", 601723), ("Seattle", "WA", 608660),
           ("Springfield", "IL", 114000), ("Fort Wayne", "IN", 253691), ("San Antonio", "TX", 1400000), ("Dublin", "CA", 46000), ("New York", "NY", 8175133), ("Albany", "NY", 97856), ("NY", "NY", 700)],
    "IN": [("Mumbai", "16", 12691836), ("New Delhi", "07", 249998), ("Delhi", "07", 10927986), ("Pune", "16", 3124458), ("Jaipur", "24", 3046163),
           ("Juhu", "16", 30000), ("Noida", "36", 642381), ("Chandigarh", "05", 960787)],
}


def make_gazetteer() -> Gazetteer:
    gaz = Gazetteer()
    for country, rows in PLACES.items():
        for name, admin1, pop in rows:
            gaz.add(country, name, Place(name, country, admin1, pop))
    return gaz


@pytest.fixture(scope="session")
def gaz():
    return make_gazetteer()


@pytest.fixture(scope="session")
def engine(gaz):
    return RulesEngine(gazetteer=gaz)


@pytest.fixture(scope="session")
def ctx(engine):
    return engine.ctx


@pytest.fixture
def run(ctx):
    """run(lines, "country postcode region", hint=None) -> state after those rules (normalise is always first)."""
    def _run(lines, rules="normalise country", hint=None):
        state = ParseState(raw_lines=list(lines), country_hint=hint)
        ids = rules.split()
        if ids[0] != "normalise":
            ids.insert(0, "normalise")
        for rid in ids:
            state = REGISTRY[rid](ctx).apply(state)
        return state
    return _run
