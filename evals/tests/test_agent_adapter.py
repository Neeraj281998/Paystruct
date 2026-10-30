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
            {"id": "b", "country": "IN", "raw_lines": NEEDS_LLM_LINES, "gold": dict(GOOD), "tags": ["x"], "difficulty": "medium"},
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


def test_run_records_keep_per_record_details_for_dev_and_calibration_only():
    system = Agent(client=ScriptedClient([submit(GOOD)]), engine=ENGINE)
    evals = run.run_system(system, records())
    dev = run.build_record(system, "dev", records(), evals)
    assert len(dev["records"]) == 3
    r = dev["records"][1]            # the record that reached the model
    for key in ("id", "raw_lines", "gold", "output", "route", "exact", "wrong", "missing", "latency_ms", "cost_usd", "system_extra"):
        assert key in r
    extra = r["system_extra"]
    assert extra["rules"]["fields"] and extra["rules"]["route"] == "NEEDS_LLM" and extra["rules"]["how_set"]
    assert extra["attempt_log"][0]["proposal"] == GOOD and extra["attempt_log"][0]["confidence"] > 0.85 and extra["attempt_log"][0]["unsupported"] == []
    assert [s["tool"] for s in extra["steps"]] == ["llm_call", "submit_repair"] and extra["confidence"] == extra["attempt_log"][0]["confidence"]
    assert "records" in run.build_record(system, "calibration", records(), evals)
    for split in ("hard", "test"):          # counts only: nobody reads individual failures there
        assert "records" not in run.build_record(system, split, records(), evals)


def test_rerun_chosen_ids_with_rules_only(tmp_path):
    p = subprocess.run([sys.executable, "-m", "evals.run", "--system", "rules_only", "--split", "dev", "--ids", "ca-00000,de-00000", "--out-dir", str(tmp_path)],
                       capture_output=True, text=True, cwd=guards.REPO_ROOT)
    assert p.returncode == 0, p.stderr
    rec = json.loads(next(tmp_path.iterdir()).read_text())
    assert rec["n_records"] == 2 and [r["id"] for r in rec["records"]] == ["ca-00000", "de-00000"] and rec["subset"].startswith("ids-") and rec["ids"]
    bad = subprocess.run([sys.executable, "-m", "evals.run", "--system", "rules_only", "--split", "dev", "--ids", "nope-1", "--out-dir", str(tmp_path)],
                         capture_output=True, text=True, cwd=guards.REPO_ROOT)
    assert bad.returncode == 2 and "unknown record ids" in bad.stderr
    text_ = report.render(report.load_runs(tmp_path))
    assert "2 selected records of dev (ids-" in text_


def test_the_agent_accepts_ids_in_place_of_limit_under_the_same_guards():
    env = {**os.environ, "ANTHROPIC_API_KEY": "sk-ant-not-a-real-key"}
    base = [sys.executable, "-m", "evals.run", "--system", "agent", "--split", "dev"]
    both = subprocess.run([*base, "--ids", "ca-00000", "--limit", "3"], capture_output=True, text=True, cwd=guards.REPO_ROOT, env=env)
    assert both.returncode == 2 and "not both" in both.stderr
    many = subprocess.run([*base, "--ids", ",".join(f"ca-{i:05d}" for i in range(31))], capture_output=True, text=True, cwd=guards.REPO_ROOT, env=env)
    assert many.returncode == 2 and "approval" in many.stderr


def test_the_robustness_source_is_development_only_and_never_a_result(tmp_path):
    p = subprocess.run([sys.executable, "-m", "evals.run", "--system", "rules_only", "--source", "robustness", "--out-dir", str(tmp_path)],
                       capture_output=True, text=True, cwd=guards.REPO_ROOT)
    assert p.returncode == 0 and "development only, not a result" in p.stdout, p.stderr
    rec = json.loads(next(tmp_path.iterdir()).read_text())
    assert rec["split"] == "robustness" and rec["development_only"] is True and rec["n_records"] == 30 and len(rec["records"]) == 30
    assert rec["records"][0]["id"] == "IE-1" and rec["records"][0]["gold"]["BldgNm"] == "The Old Creamery"     # scored against the author's own 'want'
    subprocess.run([sys.executable, "-m", "evals.run", "--system", "rules_only", "--split", "dev", "--limit", "5", "--out-dir", str(tmp_path)],
                   capture_output=True, text=True, cwd=guards.REPO_ROOT, check=True)
    runs = report.load_runs(tmp_path)
    assert all(k[1] != "robustness" for k in runs) and len(runs) == 1
    text_ = report.render(runs)
    assert "robustness" not in text_.replace("`--source robustness`", "") and "## Not results" in text_ and "not a measure of anything" in text_


def test_the_agent_robustness_run_is_guarded_like_every_real_run():
    env = {**os.environ, "ANTHROPIC_API_KEY": "sk-ant-not-a-real-key"}
    base = [sys.executable, "-m", "evals.run", "--system", "agent", "--source", "robustness"]

    def go(*args):
        return subprocess.run([*base, *args], capture_output=True, text=True, cwd=guards.REPO_ROOT, env=env)

    assert go().returncode == 2 and "mandatory" in go().stderr
    assert "approval" in go("--limit", "31").stderr
    both = subprocess.run([*base, "--split", "dev", "--limit", "3"], capture_output=True, text=True, cwd=guards.REPO_ROOT, env=env)
    assert both.returncode == 2 and "not both" in both.stderr


def test_a_scripted_agent_run_over_the_robustness_cases_keeps_details_and_is_flagged():
    system = Agent(client=ScriptedClient([], default=reply(text("done"), stop="end_turn")), engine=ENGINE)
    recs = run.robustness_records()[:6]
    evals = run.run_system(system, recs)
    rec = run.build_record(system, "robustness", recs, evals, limit=6)
    assert rec["development_only"] is True and len(rec["records"]) == 6 and rec["config"]["prompt_version"] == "repair-v2"
