"""The llm_only baseline: one call, no tools, no loop, no rules, no verifier. Offline, with a fake client."""
import json
import os
import subprocess
import sys

import pytest

from agent.repair.prompts import CONVENTIONS, SYSTEM_PROMPT
from agent.tests.fakes import ScriptedClient, call, reply, text
from evals import guards, run
from evals.metrics import compute, evaluate_record
from evals.systems import LLM_ONLY_PROMPT_VERSION, LlmOnly, NotAvailable, llm_only_system_prompt, submit_address_tool

REC = {"id": "a", "country": "IE", "raw_lines": ["14 Main St", "Cork T12 AC34", "IE"], "tags": [], "difficulty": "easy",
       "gold": {"BldgNb": "14", "StrtNm": "Main St", "TwnNm": "Cork", "PstCd": "T12 AC34", "Ctry": "IE"}}
GOOD = dict(REC["gold"])


def system(*replies):
    return LlmOnly(client=ScriptedClient(list(replies)))


def answer(fields, **kw):
    return reply(call("submit_address", fields), stop="tool_use", **kw)


def test_one_call_per_record_with_a_forced_tool_and_no_loop():
    s = system(answer(GOOD, tin=2000, tout=300))
    out = s.run(REC["raw_lines"])
    reqs = s.client.requests
    assert len(reqs) == 1 and out.route == "ACCEPT" and out.fields == GOOD
    req = reqs[0]
    assert [t["name"] for t in req["tools"]] == ["submit_address"] and req["tool_choice"] == {"type": "tool", "name": "submit_address"}
    assert "temperature" not in req and req["model"] == "claude-haiku-5-5" and len(req["messages"]) == 1
    assert out.extra["calls"] == 1 and out.extra["tokens_in"] == 2000 and out.extra["tokens_out"] == 300


def test_cost_comes_from_the_usage_and_the_same_price_table():
    out = system(answer(GOOD, tin=3000, tout=400)).run(REC["raw_lines"])
    assert out.cost_usd == pytest.approx(3000 * 0.10 / 1e6 + 400 * 0.50 / 1e6)


def test_same_conventions_text_as_the_repair_prompt_and_no_rules_or_tools_in_the_prompt():
    assert CONVENTIONS in SYSTEM_PROMPT and CONVENTIONS in llm_only_system_prompt()
    p = llm_only_system_prompt()
    for banned in ("parse_address", "validate_candidate", "country_lookup", "evidence_rules", "locked"):
        assert banned not in p
    s = system(answer(GOOD))
    s.run(REC["raw_lines"], "IE")
    msg = s.client.requests[0]["messages"][0]["content"]
    assert "<address_data id=" in msg and "Country hint from the message: IE" in msg and "untrusted data" in s.client.requests[0]["system"]
    assert "untrusted_reference_data" not in msg           # no rules result is shown
    assert LLM_ONLY_PROMPT_VERSION == "llm-only-v1" and s.config()["verifier"] == "none" and s.config()["rules"] == "none"


def test_a_wrong_but_parsable_answer_is_accepted_and_counted_as_a_false_repair():
    wrong = dict(GOOD, StrtNm="Main Road")
    out = system(answer(wrong)).run(REC["raw_lines"])
    e = evaluate_record(REC, out)
    assert out.route == "ACCEPT" and not e.score.exact
    m = compute([e])
    assert m["false_repair"]["k"] == 1 and m["false_repair"]["n"] == 1 and m["auto_correct"]["k"] == 0


def test_invented_values_are_counted_as_hallucinated_the_same_way_as_for_the_other_systems():
    invented = dict(GOOD, TwnNm="Dublin", PstCd="D02 X285")                         # not in the input
    e = evaluate_record(REC, system(answer(invented)).run(REC["raw_lines"]))
    assert sorted(e.hallucinated) == ["PstCd", "TwnNm"]
    assert compute([e])["hallucinated_values"] == 2
    expansion = dict(GOOD, StrtNm="Main Street")                                    # an allowlisted expansion is not a hallucination
    assert evaluate_record(REC, system(answer(expansion)).run(REC["raw_lines"])).hallucinated == []


def test_malformed_output_is_no_output_and_routes_review():
    bad_schema = answer({"TwnNm": "Cork", "Bogus": "x"})                              # unknown element
    wrong_type = answer({"TwnNm": 12})                                                # not a string
    no_tool = reply(text("here is the address"), stop="end_turn")
    other_tool = reply(call("approve_payment", {"id": 1}))
    for r in (bad_schema, wrong_type, no_tool, other_tool):
        out = system(r).run(REC["raw_lines"])
        assert out.route == "REVIEW" and out.fields == {} and out.extra["malformed"] is True
    e = evaluate_record(REC, system(no_tool).run(REC["raw_lines"]))
    m = compute([e])
    assert m["false_repair"]["n"] == 0 and m["routes"]["REVIEW"]["k"] == 1 and m["hallucinated_values"] == 0


def test_an_api_error_is_no_output_and_there_is_no_retry():
    s = system(RuntimeError("boom"), answer(GOOD))
    out = s.run(REC["raw_lines"])
    assert out.route == "REVIEW" and out.extra["error"] == "RuntimeError" and len(s.client.requests) == 1 and len(s.client.script) == 1


def test_adrline_is_kept_aside_and_the_answer_is_still_accepted():
    out = system(answer({"TwnNm": "Cork", "Ctry": "IE", "AdrLine": ["14 Main St"]})).run(REC["raw_lines"])
    assert out.route == "ACCEPT" and out.fields == {"TwnNm": "Cork", "Ctry": "IE"} and out.extra["adr_lines"] == ["14 Main St"]


def test_no_key_means_not_available(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = LlmOnly()
    assert s.available is False and "ANTHROPIC_API_KEY" in s.unavailable_reason
    with pytest.raises(NotAvailable):
        s.run(["x"])


def test_budget_abort_stops_the_run():
    s = system(*[answer(GOOD, tin=90_000, tout=100_000) for _ in range(5)])           # about $0.059 a call
    recs = [dict(REC, id=str(i)) for i in range(5)]
    logs = []
    evals = run.run_system(s, recs, budget_usd=0.10, log=logs.append)
    assert len(evals) == 2 and "run budget" in logs[0] and len(s.client.requests) == 2


def test_the_run_record_keeps_tokens_and_cost_per_call_for_dev():
    s = system(answer(GOOD, tin=2500, tout=350))
    evals = run.run_system(s, [REC])
    rec = run.build_record(s, "dev", [REC], evals, limit=1)
    d = rec["records"][0]
    assert rec["system"] == "llm_only" and rec["config"]["prompt_version"] == "llm-only-v1" and rec["metrics"]["cost_usd_total"] > 0
    assert d["system_extra"]["tokens_in"] == 2500 and d["system_extra"]["tokens_out"] == 350 and d["cost_usd"] == rec["metrics"]["cost_usd_total"]
    assert "records" not in run.build_record(s, "hard", [REC], evals)


def test_the_tool_schema_is_the_agents_address_schema():
    from agent.repair.tools import ADDRESS_SCHEMA
    assert submit_address_tool()["input_schema"] is ADDRESS_SCHEMA and submit_address_tool()["name"] == "submit_address"


def test_estimate_for_llm_only_is_measured_once_a_run_record_exists_and_labelled_before(tmp_path):
    from agent.repair.config import Prices
    from agent.repair.estimate import estimate_llm_only_run
    before = estimate_llm_only_run(100, Prices.load(), "claude-haiku-5-5", tmp_path)
    assert "stated assumption" in before["basis"]          # no llm_only run record and no agent record: nothing to measure from
    assert before["expected_usd"] is None
    rec = {"system": "llm_only", "records": [{"cost_usd": 0.0006, "system_extra": {"tokens_in": 2000, "tokens_out": 300}} for _ in range(10)]}
    (tmp_path / "llm.json").write_text(json.dumps(rec))
    after = estimate_llm_only_run(100, Prices.load(), "claude-haiku-5-5", tmp_path)
    assert after["basis"] == "measured" and after["measured_from"] == "llm.json" and after["expected_usd"] == pytest.approx(0.06)


def test_cli_refuses_without_limit_and_needs_a_key():
    base = [sys.executable, "-m", "evals.run", "--system", "llm_only", "--split", "dev"]
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    p = subprocess.run(base, capture_output=True, text=True, cwd=guards.REPO_ROOT, env=env)
    assert p.returncode == 3 and "ANTHROPIC_API_KEY" in p.stdout
    env["ANTHROPIC_API_KEY"] = "sk-ant-not-a-real-key"
    p = subprocess.run(base, capture_output=True, text=True, cwd=guards.REPO_ROOT, env=env)
    assert p.returncode == 2 and "mandatory" in p.stderr


def test_tuning_runs_default_to_a_fifty_cent_budget(monkeypatch, tmp_path):
    monkeypatch.delenv("PAYSTRUCT_RUN_BUDGET_USD", raising=False)
    assert run.TUNING_BUDGET_DEFAULT == "0.50"
    assert run.main(["--system", "rules_only", "--split", "dev", "--limit", "2", "--out-dir", str(tmp_path)]) == 0
    assert os.environ["PAYSTRUCT_RUN_BUDGET_USD"] == "0.50"
    monkeypatch.setenv("PAYSTRUCT_RUN_BUDGET_USD", "0.10")
    run.main(["--system", "rules_only", "--split", "dev", "--limit", "2", "--out-dir", str(tmp_path)])
    assert os.environ["PAYSTRUCT_RUN_BUDGET_USD"] == "0.10"        # the owner's value wins
