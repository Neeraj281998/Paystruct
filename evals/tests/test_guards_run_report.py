import json
import subprocess
import sys

import pytest

from evals import guards, report, run
from evals.metrics import compute, evaluate_record
from evals.systems import Agent, LlmOnly, NotAvailable, RulesOnly, SystemOutput


# -- guards ----------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("split", ["dev", "calibration", "hard"])
def test_free_and_explicit_splits_are_allowed(split):
    assert guards.check_split(split).split == split


def test_test_without_final_is_refused():
    with pytest.raises(guards.Refused, match="--final"):
        guards.check_split("test")
    with pytest.raises(guards.Refused, match="--final"):
        guards.check_split("test", final=False, test_enabled=True)


def test_test_with_final_is_still_refused_in_this_session():
    assert guards.TEST_RUN_ENABLED is False
    with pytest.raises(guards.Refused, match="not enabled"):
        guards.check_split("test", final=True)


def test_when_enabled_the_frozen_hash_is_checked_first():
    with pytest.raises(guards.Refused, match="not intact"):
        guards.check_split("test", final=True, test_enabled=True, verify=lambda: "test.jsonl has changed")
    d = guards.check_split("test", final=True, test_enabled=True, verify=lambda: None)
    assert d.split == "test" and "ONCE" in d.warning


def test_unknown_splits_are_refused():
    with pytest.raises(guards.Refused):
        guards.check_split("whatever")


def test_the_cli_refuses_test_and_writes_nothing(tmp_path):
    for extra in ([], ["--final"]):
        p = subprocess.run([sys.executable, "-m", "evals.run", "--system", "rules_only", "--split", "test", "--out-dir", str(tmp_path), *extra],
                           capture_output=True, text=True, cwd=guards.REPO_ROOT)
        assert p.returncode == 2 and "refused" in (p.stderr + p.stdout).lower()
        assert list(tmp_path.iterdir()) == []


def test_the_evals_code_never_reads_the_test_file_directly():
    import inspect
    import evals.metrics, evals.run, evals.report, evals.systems
    for mod in (evals.metrics, evals.run, evals.report, evals.systems):
        assert "test.jsonl" not in inspect.getsource(mod)


# -- systems ---------------------------------------------------------------------------------------------------------
def test_llm_only_is_a_stub_and_the_agent_needs_a_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    s = LlmOnly()
    assert s.available is False and "not yet available" in s.unavailable_reason
    with pytest.raises(NotAvailable):
        s.run(["x"])
    a = Agent()
    assert a.available is False and "ANTHROPIC_API_KEY" in a.unavailable_reason
    with pytest.raises(NotAvailable):
        a.run(["x"])


def test_rules_only_returns_fields_route_latency_and_zero_cost():
    out = RulesOnly().run(["64B Market Square", "Kilkenny R95 NRC2", "Ireland"])
    assert out.route in ("ACCEPT", "NEEDS_LLM", "REVIEW") and out.cost_usd == 0.0 and out.latency_s > 0 and "Ctry" in out.fields


def _env_without_key():
    import os
    return {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}


def test_the_stub_and_the_keyless_agent_write_no_record(tmp_path):
    for system, expect in (("llm_only", "not yet available"), ("agent", "ANTHROPIC_API_KEY")):
        p = subprocess.run([sys.executable, "-m", "evals.run", "--system", system, "--split", "dev", "--limit", "5", "--out-dir", str(tmp_path)],
                           capture_output=True, text=True, cwd=guards.REPO_ROOT, env=_env_without_key())
        assert p.returncode == 3 and expect in p.stdout and list(tmp_path.iterdir()) == []


# -- run records -----------------------------------------------------------------------------------------------------
class Fake:
    name = "fake"

    def config(self):
        return {"model": None, "prompt_version": None, "thresholds": {"accept": 0.8}}


def test_a_run_record_has_everything_the_decision_requires(tmp_path):
    rec = {"id": "x", "country": "IE", "raw_lines": ["14 Main St", "Cork T12 AC34"], "gold": {"TwnNm": "Cork", "Ctry": "IE"}, "tags": [], "difficulty": "easy"}
    ev = [evaluate_record(rec, SystemOutput({"TwnNm": "Cork", "Ctry": "IE"}, "ACCEPT", 0.001))]
    record = run.build_record(Fake(), "dev", [rec], ev, seed=7, split_sha="abc")
    for key in ("git_sha", "split", "n_records", "system", "config", "seed", "date", "metrics", "split_sha256"):
        assert key in record
    path = run.write_record(record, tmp_path)
    again = json.loads(path.read_text())
    assert again["seed"] == 7 and again["n_records"] == 1 and again["metrics"]["exact_all"]["k"] == 1 and len(again["git_sha"]) >= 7


# -- report ----------------------------------------------------------------------------------------------------------
def make_run(tmp_path, system, split, wrong):
    recs = [{"id": f"r{i}", "country": "IE", "raw_lines": ["14 Main St", "Cork T12 AC34"],
             "gold": {"BldgNb": "14", "TwnNm": "Cork", "Ctry": "IE"}, "tags": ["county"] if i % 2 else [], "difficulty": "easy"} for i in range(10)]
    evs = []
    for i, r in enumerate(recs):
        f = dict(r["gold"])
        if i < wrong:
            f["TwnNm"] = "Dublin"
        evs.append(evaluate_record(r, SystemOutput(f, "ACCEPT", 0.001)))
    system_obj = Fake()
    system_obj.name = system
    path = run.write_record(run.build_record(system_obj, split, recs, evs), tmp_path)
    return path


def test_the_report_comes_from_run_records_only(tmp_path):
    make_run(tmp_path, "rules_only", "dev", wrong=2)
    out = tmp_path / "eval-results.md"
    assert report.main(["--results-dir", str(tmp_path), "--out", str(out)]) == 0
    text = out.read_text()
    assert "| rules_only | 10 |" in text and "20.0% (2/10)" in text          # the false-repair rate, k/n beside it
    assert "| llm_only | not run yet" in text and "| agent | not run yet" in text
    assert "Dataset size: 10 records" in text and "git `" in text and "run 20" in text
    assert "## hard" in text and "No run records for `hard`" in text and "Not run yet" in text   # test section, never run


def test_the_report_changes_when_the_run_changes(tmp_path):
    make_run(tmp_path, "rules_only", "dev", wrong=0)
    a = report.render(report.load_runs(tmp_path))
    for f in tmp_path.glob("*.json"):
        f.unlink()
    make_run(tmp_path, "rules_only", "dev", wrong=5)
    b = report.render(report.load_runs(tmp_path))
    assert a != b and "50.0% (5/10)" in b and "0.0% (0/10)" in a


def test_small_buckets_show_counts_not_percentages_in_the_report(tmp_path):
    make_run(tmp_path, "rules_only", "dev", wrong=1)
    text = report.render(report.load_runs(tmp_path))
    # 'county' tag has 5 records (shown with a rate); a 4-record bucket would show k/n only
    assert "| IE | 10 |" in text


def test_the_report_uses_the_latest_run_per_system_and_split(tmp_path):
    p1 = make_run(tmp_path, "rules_only", "dev", wrong=9)
    d = json.loads(p1.read_text())
    d["date"] = "2000-01-01T00:00:00Z"
    p1.write_text(json.dumps(d))
    make_run(tmp_path, "rules_only", "dev", wrong=0)
    assert report.load_runs(tmp_path)[("rules_only", "dev", None)]["metrics"]["false_repair"]["k"] == 0


def test_the_hard_set_note_is_generated_from_records(tmp_path):
    make_run(tmp_path, "rules_only", "hard", wrong=3)
    make_run(tmp_path, "rules_only", "dev", wrong=0)
    out = tmp_path / "note.md"
    assert report.main(["--results-dir", str(tmp_path), "--out", str(out), "--hard-set-note"]) == 0
    text = out.read_text()
    assert "N = 10" in text and "30.0% (3/10)" in text and "small, AI-drafted and AI-verified" in text and "read on Day 1" in text
    assert "dev is optimistic" in text.lower()
    assert report.render_hard_note({}).strip().endswith("No hard-set run record yet.")
