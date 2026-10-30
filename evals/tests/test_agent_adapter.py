"""The agent as an evaluation system, offline with a scripted model: same interface, same run records."""
import json
import os
import subprocess
import sys

from agent.rules.engine import RulesEngine
from agent.tests.conftest import make_gazetteer
from agent.tests.fakes import GOOD, NEEDS_LLM_LINES, ScriptedClient, reply, submit, text
from evals import guards, report, run
from evals.metrics import compute
from evals.systems import Agent

ENGINE = RulesEngine(gazetteer=make_gazetteer())


def records():
    gold = {"BldgNb": "14", "StrtNm": "Main St", "TwnNm": "Cork", "PstCd": "T12 AC34", "Ctry": "IE"}
    return [{"id": "a", "country": "IE", "raw_lines": ["14 Main St", "Cork T12 AC34", "IE"], "gold": gold, "tags": [], "difficulty": "easy"},
            {"id": "b", "country": "IE", "raw_lines": NEEDS_LLM_LINES, "gold": gold, "tags": ["x"], "difficulty": "medium"},
            {"id": "c", "country": "FR", "raw_lines": ["27 rue des Acacias", "69003", "France"], "gold": {"BldgNb": "27", "StrtNm": "rue des Acacias", "PstCd": "69003", "Ctry": "FR"},
             "tags": ["no_town"], "difficulty": "hard"}]


def test_the_agent_system_has_the_common_interface_and_cost():
    client = ScriptedClient([submit(GOOD, tin=3000, tout=400)])
    system = Agent(client=client, engine=ENGINE)
    assert system.available and system.name == "agent"
    outs = [system.run(r["raw_lines"], None) for r in records()]
    assert [o.route for o in outs] == ["ACCEPT", "ACCEPT", "REVIEW"]            # rules accept, model repair, no town -> review
    assert outs[0].cost_usd == 0 and outs[1].cost_usd > 0 and outs[2].cost_usd == 0
    assert outs[2].fields.get("TwnNm") is None and system.total_cost == outs[1].cost_usd
    assert len(client.requests) == 1                                           # only the NEEDS_LLM record reached the model
    assert system.config()["model"] == "claude-haiku-5-5" and system.config()["prompt_version"]


def test_the_agent_run_record_has_the_same_shape_and_a_cost(tmp_path):
    system = Agent(client=ScriptedClient([submit(GOOD, tin=3000, tout=400)]), engine=ENGINE)
    evals = run.run_system(system, records())
    rec = run.build_record(system, "dev", records(), evals, limit=3)
    for key in ("git_sha", "split", "n_records", "system", "config", "seed", "date", "metrics", "limit"):
        assert key in rec
    m = rec["metrics"]
    assert m["cost_usd_total"] > 0 and m["cost_per_1000_usd"] > 0 and m["false_repair"]["n"] == 2 and m["false_repair"]["k"] == 0
    assert m["no_town"]["n"] == 1 and m["no_town"]["output_a_town"] == 0 and m["hallucinated_values"] == 0
    path = run.write_record(rec, tmp_path)
    assert "first3" in path.name


def test_run_system_stops_at_the_run_budget():
    script = [submit(GOOD, tin=90_000, tout=100_000)] * 5
    system = Agent(client=ScriptedClient(script), engine=ENGINE)
    recs = [dict(records()[1], id=str(i)) for i in range(5)]
    logs = []
    evals = run.run_system(system, recs, budget_usd=0.10, log=logs.append)
    assert len(evals) == 2 and "run budget" in logs[0]
    rec = run.build_record(system, "dev", recs, evals, limit=5)
    assert rec["aborted_by_budget"] is True and rec["n_records"] == 2


def test_the_report_shows_the_first_n_table_with_every_system(tmp_path):
    system = Agent(client=ScriptedClient([submit(GOOD)]), engine=ENGINE)
    run.write_record(run.build_record(system, "dev", records(), run.run_system(system, records()), limit=3), tmp_path)
    from evals.systems import RulesOnly
    ro = RulesOnly(engine=ENGINE)
    run.write_record(run.build_record(ro, "dev", records(), run.run_system(ro, records()), limit=3), tmp_path)
    text_ = report.render(report.load_runs(tmp_path))
    assert "**First 3 records of dev**" in text_ and "| agent | 3 |" in text_ and "| rules_only | 3 |" in text_ and "| llm_only | not run yet" in text_
    assert "model claude-haiku-5-5" in text_


def test_evals_cli_guards_for_the_agent():
    env = {**os.environ, "ANTHROPIC_API_KEY": "sk-ant-not-a-real-key"}
    base = [sys.executable, "-m", "evals.run", "--system", "agent"]

    def go(*args):
        return subprocess.run([*base, *args], capture_output=True, text=True, cwd=guards.REPO_ROOT, env=env)

    p = go("--split", "calibration", "--limit", "5")
    assert p.returncode == 2 and "runs on dev only" in p.stderr
    for split in ("hard", "test"):
        assert go("--split", split, "--limit", "5").returncode == 2
    p = go("--split", "dev")
    assert p.returncode == 2 and "--limit" in p.stderr
    p = go("--split", "dev", "--limit", "31")
    assert p.returncode == 2 and "approval" in p.stderr
    p = go("--split", "dev", "--limit", "60", "--approved-over-30")
    assert p.returncode == 2 and "--yes" in p.stderr
    assert "sk-ant-not-a-real-key" not in p.stdout + p.stderr
