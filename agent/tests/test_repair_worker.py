import json
import subprocess
import sys

import pytest

from agent.repair import worker
from agent.repair.store import InMemoryRepository
from agent.rules.xsd import REPO_ROOT

from .fakes import GOOD, NEEDS_LLM_LINES, make_pipeline, submit


def cli(*args, env=None):
    import os
    e = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY",)}
    e.update(env or {})
    return subprocess.run([sys.executable, "-m", "agent.repair.worker", *args], capture_output=True, text=True, cwd=REPO_ROOT, env=e)


def test_limit_is_mandatory():
    p = cli("--source", "dev", "--no-llm", "--memory")
    assert p.returncode == 2 and "--limit" in p.stderr


def test_a_real_run_needs_a_key_and_a_key_is_never_asked_for():
    p = cli("--source", "dev", "--limit", "3", "--memory")
    assert p.returncode == 2 and "ANTHROPIC_API_KEY is not set" in p.stderr and "--no-llm" in p.stderr


def test_more_than_30_real_records_need_the_owners_approval_and_more_than_50_need_yes():
    p = cli("--source", "dev", "--limit", "31", "--memory", env={"ANTHROPIC_API_KEY": "sk-ant-not-a-real-key"})
    assert p.returncode == 2 and "approval" in p.stderr
    p = cli("--source", "dev", "--limit", "60", "--memory", "--approved-over-30", env={"ANTHROPIC_API_KEY": "sk-ant-not-a-real-key"})
    assert p.returncode == 2 and "--yes" in p.stderr and "estimate" in p.stdout and "would_reach_the_model" in p.stdout
    assert "sk-ant-not-a-real-key" not in p.stdout + p.stderr


def test_the_agent_runs_on_dev_only_today():
    with pytest.raises(SystemExit, match="REFUSED"):
        worker.load_jsonl("calibration", 5)
    with pytest.raises(SystemExit, match="REFUSED"):
        worker.load_jsonl("hard", 5)
    with pytest.raises(SystemExit, match="REFUSED"):
        worker.load_jsonl("test", 5)
    import inspect
    assert "test.jsonl" not in inspect.getsource(worker) and "hard.jsonl" not in inspect.getsource(worker)


def test_no_llm_run_needs_no_key_and_no_network():
    p = cli("--source", "dev", "--limit", "20", "--no-llm", "--memory")
    assert p.returncode == 0, p.stderr
    res = json.loads(p.stdout.strip().splitlines()[-1])
    assert res["processed"] == 20 and res["cost_usd"] == 0 and res["repaired"] + res["review"] == 20


def test_the_run_budget_aborts_the_run():
    expensive = [submit(GOOD, tin=90_000, tout=100_000) for _ in range(5)]
    p = make_pipeline(expensive, routing_overrides={"max_cost_usd_per_payment": 1.0})
    items = [(f"m{i}", NEEDS_LLM_LINES, None) for i in range(5)]
    logs = []
    res = worker.run(items, p, budget_usd=0.10, log=logs.append)
    assert res["processed"] == 2 and res["cost_usd"] == pytest.approx(2 * 0.059) and "run budget" in logs[0]


def test_duplicate_deliveries_in_one_run_are_skipped():
    p = make_pipeline([submit(GOOD)], repo=InMemoryRepository())
    res = worker.run([("same", NEEDS_LLM_LINES, None), ("same", NEEDS_LLM_LINES, None)], p, budget_usd=1.0)
    assert res["repaired"] == 1 and res["skipped"] == 1 and len(p.client.requests) == 1
