"""Guards from the Day 2 audit: the scorer cannot be fooled by shifted gold, and the rules matter."""
from agent.audit.audit_dev import run, without
from agent.rules.cli import load_split
from agent.rules.engine import RulesEngine
from agent.rules.scoring import score_record

RECORDS = load_split("dev")[:200]


def test_predictions_scored_against_another_records_gold_are_almost_never_exact():
    engine = RulesEngine()
    preds = [engine.parse(r["raw_lines"], r.get("country_hint")).fields for r in RECORDS]
    n = len(RECORDS)
    hits = sum(score_record(preds[i], RECORDS[(i + 1) % n]["gold"], RECORDS[(i + 1) % n]["country"]).exact for i in range(n))
    assert hits / n < 0.02


def test_disabling_a_core_rule_makes_dev_accuracy_collapse():
    base, _ = run(RECORDS, RulesEngine())
    for rule in ("postcode", "street", "country", "town"):
        broken, _ = run(RECORDS, without(rule))
        assert broken["exact"] < base["exact"] - 40, rule


def test_the_engine_needs_no_country_hint_to_be_correct():
    base, _ = run(RECORDS, RulesEngine(), use_hint=True)
    nohint, _ = run(RECORDS, RulesEngine(), use_hint=False)
    assert nohint["exact"] >= base["exact"] - 3
