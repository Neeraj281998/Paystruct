import math

import pytest

from evals.metrics import compute, evaluate_record, hallucinated_fields
from evals.stats import fmt, percentile, rate, wilson
from evals.systems import SystemOutput


def out(fields, route="ACCEPT", latency=0.001, cost=0.0):
    return SystemOutput(fields, route, latency, cost)


def rec(rid, country, raw, gold, tags=(), tier="easy"):
    return {"id": rid, "country": country, "raw_lines": raw, "gold": gold, "tags": list(tags), "difficulty": tier}


R_IE = rec("a", "IE", ["14 Main St", "Cork T12 AC34", "IE"], {"BldgNb": "14", "StrtNm": "Main St", "TwnNm": "Cork", "PstCd": "T12 AC34", "Ctry": "IE"}, tier="easy")
R_NT = rec("b", "FR", ["27 rue des Acacias", "69003", "France"], {"BldgNb": "27", "StrtNm": "rue des Acacias", "PstCd": "69003", "Ctry": "FR"}, ["no_town"], "hard")


# -- stats -----------------------------------------------------------------------------------------------------------
def test_wilson_matches_known_values():
    lo, hi = wilson(8, 10)
    assert lo == pytest.approx(0.4902, abs=1e-3) and hi == pytest.approx(0.9433, abs=1e-3)
    assert wilson(0, 10)[0] == 0.0 and wilson(10, 10)[1] == 1.0 and wilson(0, 0) is None
    lo, hi = wilson(50, 100)
    assert lo == pytest.approx(0.4038, abs=1e-3) and hi == pytest.approx(0.5962, abs=1e-3)


def test_percentile_nearest_rank():
    assert percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 50) == 5 and percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95) == 10
    assert percentile([], 50) == 0.0 and percentile([7], 95) == 7


def test_small_buckets_print_counts_only():
    assert rate(3, 4)["rate"] is None and fmt(rate(3, 4)) == "3/4"
    assert fmt(rate(5, 5)) == "100.0% (5/5)" and fmt(rate(0, 0)).startswith("-")
    assert "[" in fmt(rate(8, 10), ci=True)


# -- hallucinated values ---------------------------------------------------------------------------------------------
def test_values_built_from_the_input_are_not_hallucinated():
    assert hallucinated_fields({"StrtNm": "Main St", "TwnNm": "cork", "Ctry": "IE"}, R_IE["raw_lines"], "IE") == []


def test_allowlisted_expansions_are_exempt_but_other_words_are_not():
    assert hallucinated_fields({"StrtNm": "Main Street"}, R_IE["raw_lines"], "IE") == []
    assert hallucinated_fields({"StrtNm": "Main Boulevard"}, R_IE["raw_lines"], "IE") == ["StrtNm"]


def test_the_country_code_is_the_one_value_that_may_be_added():
    assert hallucinated_fields({"Ctry": "GB"}, ["somewhere"], "IE") == []
    assert hallucinated_fields({"TwnNm": "Dublin"}, ["somewhere"], "IE") == ["TwnNm"]


# -- metrics on tiny examples -----------------------------------------------------------------------------------------
def test_perfect_system():
    evals = [evaluate_record(R_IE, out(dict(R_IE["gold"]))), evaluate_record(R_NT, out({k: v for k, v in R_NT["gold"].items()}))]
    m = compute(evals)
    assert m["exact_all"]["k"] == 2 and m["false_repair"]["k"] == 0 and m["false_repair"]["n"] == 2 and m["hallucinated_values"] == 0
    assert m["field_accuracy"]["k"] == m["field_accuracy"]["n"] == 9 and m["auto_correct"]["k"] == 2


def test_a_deliberately_wrong_fake_system_is_counted_as_wrong():
    wrong_town = dict(R_IE["gold"], TwnNm="Dublin")          # wrong, and not in the input: a hallucination
    wrong_street = dict(R_IE["gold"], StrtNm="Main Road")    # wrong, not a hallucination only if 'Road' is in the input (it is not)
    extra = dict(R_IE["gold"], TwnLctnNm="Cork")             # extra field, built from the input
    missing = {k: v for k, v in R_IE["gold"].items() if k != "BldgNb"}
    evals = [evaluate_record(R_IE, out(f)) for f in (wrong_town, wrong_street, extra, missing)]
    m = compute(evals)
    assert m["exact_all"]["k"] == 0
    assert m["false_repair"]["k"] == 4 and m["false_repair"]["n"] == 4          # all ACCEPT and all wrong
    assert m["auto_correct"]["k"] == 0
    assert m["hallucinated_values"] == 2 and m["hallucinated_by_element"] == {"TwnNm": 1, "StrtNm": 1}
    assert m["per_element"]["TwnNm"]["fp"] == 1 and m["per_element"]["TwnNm"]["fn"] == 1 and m["per_element"]["BldgNb"]["fn"] == 1
    assert m["per_element"]["TwnLctnNm"]["fp"] == 1
    assert dict(m["failure_patterns"])["TwnNm:wrong"] == 1


def test_only_accept_records_count_towards_the_false_repair_rate():
    wrong = dict(R_IE["gold"], TwnNm="Dublin")
    evals = [evaluate_record(R_IE, out(wrong, "NEEDS_LLM")), evaluate_record(R_IE, out(dict(R_IE["gold"]), "ACCEPT")),
             evaluate_record(R_IE, out(wrong, "REVIEW"))]
    m = compute(evals)
    assert m["false_repair"]["n"] == 1 and m["false_repair"]["k"] == 0
    assert m["not_repaired"]["k"] == 2 and m["auto_correct"]["k"] == 1
    assert [m["routes"][r]["k"] for r in ("ACCEPT", "NEEDS_LLM", "REVIEW")] == [1, 1, 1]


def test_exact_all_ignores_routing():
    e = evaluate_record(R_IE, out(dict(R_IE["gold"]), "NEEDS_LLM"))
    assert compute([e])["exact_all"]["k"] == 1 and compute([e])["auto_correct"]["k"] == 0


def test_no_town_gold_with_an_output_town_is_wrong():
    invented = dict(R_NT["gold"], TwnNm="Lyon")                # not in the input: wrong AND hallucinated
    from_input = dict(R_NT["gold"], TwnNm="Acacias")            # in the input: wrong, not hallucinated
    clean = dict(R_NT["gold"])
    evals = [evaluate_record(R_NT, out(f)) for f in (invented, from_input, clean)]
    m = compute(evals)
    assert evals[0].score.exact is False and evals[1].score.exact is False and evals[2].score.exact is True
    nt = m["no_town"]
    assert nt["n"] == 3 and nt["output_a_town"] == 2 and nt["hallucinated_town"] == 1 and nt["accepted_with_a_town"] == 2
    assert m["hallucinated_by_element"] == {"TwnNm": 1}


def test_latency_cost_and_breakdowns():
    evals = [evaluate_record(R_IE, out(dict(R_IE["gold"]), latency=0.001 * (i + 1), cost=0.002)) for i in range(10)]
    evals.append(evaluate_record(R_NT, out(dict(R_NT["gold"]), latency=0.1, cost=0.0)))
    m = compute(evals)
    assert m["latency_ms"]["p50"] == pytest.approx(6.0) and m["latency_ms"]["p95"] == pytest.approx(100.0)
    assert m["cost_per_1000_usd"] == pytest.approx(1000 * 0.02 / 11, rel=1e-4)
    assert m["by_country"]["IE"]["n"] == 10 and m["by_country"]["FR"]["exact_all"]["rate"] is None   # 1 record: counts only
    assert m["by_country"]["IE"]["exact_all"]["rate"] == 1.0
    assert m["by_tier"]["hard"]["n"] == 1 and m["by_tag"]["no_town"]["n"] == 1 and m["by_tag"]["untagged"]["n"] == 10


def test_scoring_is_the_agent_rules_scorer():
    import agent.rules.scoring as sc
    import evals.metrics as em
    assert em.score_record is sc.score_record
    # allowlist pairs are equal through that scorer
    e = evaluate_record(R_IE, out(dict(R_IE["gold"], StrtNm="Main Street")))
    assert e.score.exact
