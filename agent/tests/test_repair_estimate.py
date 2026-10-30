"""The cost estimate: rules offline, cost per model-handled record measured from a run record, never typed in."""
import json
from pathlib import Path

import pytest

from agent.repair import estimate
from agent.repair.config import Prices, load_routing
from agent.rules.engine import RulesEngine
from agent.rules.xsd import REPO_ROOT

from .conftest import make_gazetteer
from .fakes import ELIMINATION_ONLY_LINES, NEEDS_LLM_LINES

ENGINE = RulesEngine(gazetteer=make_gazetteer())
ROUTING = load_routing()
RUN = REPO_ROOT / "evals" / "results" / "20261030T141533Z_agent_robustness_first30_093ead5.json"


def fake_run(tmp_path, per_record=0.03, n_handled=4, with_unhandled=2, name="r.json"):
    """A minimal agent run record: n_handled records made 2 model calls each at per_record dollars; the others made none."""
    recs = []
    for i in range(n_handled):
        steps = [{"tool": "llm_call", "tokens_in": 4000, "tokens_out": 500}, {"tool": "submit_repair", "tokens_in": 0, "tokens_out": 0},
                 {"tool": "llm_call", "tokens_in": 6000, "tokens_out": 700}]
        recs.append({"cost_usd": per_record, "system_extra": {"steps": steps}})
    for i in range(with_unhandled):
        recs.append({"cost_usd": 0.0, "system_extra": {"steps": []}})
    (tmp_path / name).write_text(json.dumps({"system": "agent", "config": {"model": "claude-haiku-5-5"}, "records": recs}))
    return tmp_path


def test_measured_usage_comes_from_the_run_record_not_from_a_constant():
    run = json.loads(RUN.read_text())
    handled = [r for r in run["records"] if any(s["tool"] == "llm_call" for s in r["system_extra"]["steps"])]
    calls = sum(1 for r in handled for s in r["system_extra"]["steps"] if s["tool"] == "llm_call")
    u = estimate.measured_usage()
    assert u["file"] == RUN.name or u["model_handled_records"] >= len(handled)
    assert u["model_handled_records"] == len(handled) == 15 and u["api_calls"] == calls
    assert u["per_record_usd"] == pytest.approx(run["metrics"]["cost_usd_total"] / len(handled), rel=1e-3)
    assert u["per_call_usd"] == pytest.approx(run["metrics"]["cost_usd_total"] / calls, rel=1e-3)
    assert 0.003 < u["per_record_usd"] < 0.006      # about $0.0042 as read from the record


def test_no_run_record_means_no_measurement(tmp_path):
    assert estimate.measured_usage(tmp_path) is None
    (tmp_path / "rules.json").write_text(json.dumps({"system": "rules_only", "records": []}))
    (tmp_path / "bad.json").write_text("not json")
    assert estimate.measured_usage(tmp_path) is None


def test_the_record_with_the_most_model_handled_records_is_used(tmp_path):
    fake_run(tmp_path, per_record=0.01, n_handled=2, name="a.json")
    fake_run(tmp_path, per_record=0.02, n_handled=5, name="b.json")
    u = estimate.measured_usage(tmp_path)
    assert u["file"] == "b.json" and u["model_handled_records"] == 5 and u["per_record_usd"] == pytest.approx(0.02)


def test_only_records_that_reach_the_model_are_counted():
    items = [("a", NEEDS_LLM_LINES, None),                         # reaches the model
             ("b", ELIMINATION_ONLY_LINES, None),                    # skipped under fix 5
             ("c", ["14 Main St", "Cork T12 AC34", "IE"], None),     # rules ACCEPT
             ("d", ["27 rue des Acacias-Fleuris", "69003", "France"], None)]   # rules REVIEW (no town)
    assert estimate.count_reaching_model(items, ENGINE, ROUTING) == 1
    assert estimate.count_reaching_model([], ENGINE, ROUTING) == 0


def test_expected_and_worst_case_cost(tmp_path):
    d = fake_run(tmp_path, per_record=0.004)
    items = [("a", NEEDS_LLM_LINES, None)] * 5 + [("b", ELIMINATION_ONLY_LINES, None)] * 5
    est = estimate.estimate_agent(items, ENGINE, ROUTING, d)
    assert est["records"] == 10 and est["would_reach_the_model"] == 5
    assert est["expected_usd"] == pytest.approx(5 * 0.004) and est["per_model_record_usd"] == pytest.approx(0.004)
    assert est["worst_case_usd"] == pytest.approx(5 * 3 * 0.004)          # 3 attempts
    assert est["measured_from"] == "r.json" and est["per_payment_cap_usd"] == ROUTING["max_cost_usd_per_payment"] and est["run_budget_usd"] > 0


def test_the_worst_case_is_capped_by_the_per_payment_cap(tmp_path):
    d = fake_run(tmp_path, per_record=0.04)                                # 3 x 0.04 = 0.12 > the 0.05 cap
    est = estimate.estimate_agent([("a", NEEDS_LLM_LINES, None)] * 2, ENGINE, ROUTING, d)
    assert est["worst_case_usd"] == pytest.approx(2 * ROUTING["max_cost_usd_per_payment"])
    assert est["expected_usd"] == pytest.approx(2 * 0.04)


def test_nothing_reaching_the_model_costs_nothing(tmp_path):
    est = estimate.estimate_agent([("b", ELIMINATION_ONLY_LINES, None)] * 30, ENGINE, ROUTING, fake_run(tmp_path))
    assert est["would_reach_the_model"] == 0 and est["expected_usd"] == 0 and est["worst_case_usd"] == 0


def test_without_a_measurement_only_the_cap_bounds_the_run(tmp_path):
    est = estimate.estimate_agent([("a", NEEDS_LLM_LINES, None)] * 3, ENGINE, ROUTING, tmp_path)
    assert est["expected_usd"] is None and "no earlier agent run record" in est["note"]
    assert est["worst_case_usd"] == pytest.approx(3 * ROUTING["max_cost_usd_per_payment"])


def test_the_first_30_dev_records_would_not_reach_the_model():
    from agent.rules.cli import load_split
    items = [(r["id"], r["raw_lines"], r.get("country_hint")) for r in load_split("dev")[:30]]
    est = estimate.estimate_agent(items, RulesEngine(), ROUTING)
    assert est["records"] == 30 and est["would_reach_the_model"] == 0 and est["expected_usd"] == 0


def test_llm_only_estimate_is_labelled_and_scaled_by_a_stated_ratio(tmp_path):
    u = estimate.measured_usage(fake_run(tmp_path))
    prices = Prices.load()
    est = estimate.estimate_llm_only(100, u, prices, "claude-haiku-5-5")
    full = estimate.estimate_llm_only(100, u, prices, "claude-haiku-5-5", ratio=1.0)
    assert est["calls"] == 100 and est["prompt_size_ratio"] == estimate.LLM_ONLY_PROMPT_RATIO == 0.5
    assert "an estimate" in est["note"] and est["measured_from"] == "r.json"
    assert est["expected_usd"] < full["expected_usd"]
    # input tokens scaled, output tokens as measured
    per_call = prices.cost("claude-haiku-5-5", int(u["tokens_in_per_call"] * 0.5), int(u["tokens_out_per_call"]))
    assert est["expected_usd"] == pytest.approx(round(100 * per_call, 4))
    assert estimate.estimate_llm_only(10, None, prices, "claude-haiku-5-5")["expected_usd"] is None


def test_the_estimate_module_never_calls_the_api():
    import inspect
    src = inspect.getsource(estimate)
    assert "anthropic" not in src and "messages.create" not in src


def test_the_old_hard_coded_token_constants_are_gone():
    from agent.repair import worker
    assert not hasattr(worker, "EST_TOKENS_IN") and not hasattr(worker, "estimate")
