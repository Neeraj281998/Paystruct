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
    assert "instruction text in any published field? no" in out
    assert "no town is written" in out


@needs_gazetteer
def test_the_readme_sample_is_the_real_demo_output():
    out = run_demo("--pause", "0", env=no_key_env()).stdout.rstrip("\n")
    readme = (guards.REPO_ROOT / "README.md").read_text(encoding="utf-8")
    block = readme[readme.index("<!-- demo:start -->\n") + len("<!-- demo:start -->\n"): readme.index("\n<!-- demo:end -->")]
    assert block == out


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
