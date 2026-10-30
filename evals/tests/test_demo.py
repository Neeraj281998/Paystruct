import os
import subprocess
import sys

import pytest

from agent.rules.gazetteer import GAZETTEER_PATH
from evals import guards

SCRIPT = guards.REPO_ROOT / "scripts" / "demo.py"
needs_gazetteer = pytest.mark.skipif(not GAZETTEER_PATH.exists(), reason="the GeoNames cities500 file is not installed (README, quick start, step 3)")


def run_demo(*args, env=None):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=guards.REPO_ROOT, env=env)


def no_key_env():
    return {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}


@needs_gazetteer
def test_the_demo_runs_offline_and_exits_zero():
    p = run_demo("--pause", "0", env=no_key_env())
    assert p.returncode == 0, p.stderr
    out = p.stdout
    for n in range(1, 6):
        assert f"[{n}/5]" in out
    assert "REPAIRED" in out and "REVIEW" in out and "\033[" not in out          # piped output has no colour codes
    assert "instruction text in any published field? not tested here" in out and "would reach the model; not run offline" in out
    assert "the only open field was set by elimination" in out          # case 4: the real ELIMINATION_ONLY_NO_EVIDENCE reason
    assert "rules' own score" in out and "final confidence" in out
    assert "no town is written" in out


@needs_gazetteer
def test_the_readme_sample_is_the_real_demo_output():
    out = run_demo("--pause", "0", env=no_key_env()).stdout.rstrip("\n")
    readme = (guards.REPO_ROOT / "README.md").read_text(encoding="utf-8")
    block = readme[readme.index("<!-- raw:start -->\n") + len("<!-- raw:start -->\n"): readme.index("\n<!-- raw:end -->")]
    assert block == "```text\n" + out + "\n```"          # the markers are outside the code fence


@needs_gazetteer
def test_the_readme_how_it_works_section_is_the_generated_one():
    expected = run_demo("--markdown", env=no_key_env())
    assert expected.returncode == 0, expected.stderr
    readme = (guards.REPO_ROOT / "README.md").read_text(encoding="utf-8")
    block = readme[readme.index("<!-- demo:start -->\n") + len("<!-- demo:start -->\n"): readme.index("\n<!-- demo:end -->")]
    assert block + "\n" == expected.stdout
    assert "nothing published" in block and "<AdrLine>" in block and "not a rebuilt message" in block


def test_live_never_runs_without_a_key_and_makes_no_call():
    p = run_demo("--live", env=no_key_env())
    assert p.returncode == 2 and "ANTHROPIC_API_KEY" in p.stderr


def test_live_is_off_by_default():
    import importlib.util
    spec = importlib.util.spec_from_file_location("demo", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    import inspect
    assert "run_live(style) if args.live else" in inspect.getsource(mod.main)


@needs_gazetteer
def test_the_demo_pipeline_uses_a_stub_that_refuses_to_call_out():
    import importlib.util
    spec = importlib.util.spec_from_file_location("demo", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    pipeline, stub = mod.offline_pipeline()
    assert pipeline.agent is not None
    with pytest.raises(mod.ModelCalled):
        stub.messages.create(model="x")
    results = [mod.analyse(i, lines, hint, pipeline, stub) for i, (_c, lines, hint) in enumerate(mod.CASES, 1)]
    assert [r["status"] for r in results] == ["REPAIRED", "REPAIRED", "REVIEW", "REVIEW", mod.NOT_RUN]
    assert results[3]["out"].reasons == ["ELIMINATION_ONLY_NO_EVIDENCE"] and not results[3]["reached_model"]
    assert results[4]["reached_model"] and results[4]["out"].address() == {}


def test_the_test_split_agent_record_keeps_no_model_count():
    # the README says so; if a later record keeps one, the README sentence must change
    import json
    rec = json.loads((guards.REPO_ROOT / "evals" / "results" / "20261030T154720Z_agent_test_e7d2f7f.json").read_text())
    assert not [k for k in rec["metrics"] if "model" in k or "call" in k]
