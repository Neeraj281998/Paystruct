#!/usr/bin/env python3
"""The final runs, once, with the frozen configuration (docs/decisions/final-run-protocol.md).

Checks (all must pass): the working tree is clean, the git tag final-config exists on HEAD, scripts/verify_frozen.py passes, and
PAYSTRUCT_RUN_BUDGET_USD is set. Then it prints the estimate for every run, requires you to type FINAL, and runs in order:
all three systems on the hard set, all three on the test split with --final, and the injection slice for any system that has not run it.
It then regenerates the report. It does not change the test guard (evals/guards.py): TEST_RUN_ENABLED was flipped in its own commit, and final-config tagged on that
commit, before this script was run.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

SYSTEMS = ("rules_only", "llm_only", "agent")
MODEL_SYSTEMS = ("llm_only", "agent")
TAG = "final-config"
BUDGET_VAR = "PAYSTRUCT_RUN_BUDGET_USD"
PY = [sys.executable, "-m"]


def git(*args: str) -> tuple[int, str]:
    p = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)
    return p.returncode, p.stdout.strip()


def verify_frozen() -> str | None:
    spec = importlib.util.spec_from_file_location("verify_frozen", REPO / "scripts" / "verify_frozen.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.verify()


def preflight(env=None, git_fn=git, verify_fn=verify_frozen) -> list[str]:
    """The reasons the final run must not start (an empty list means go)."""
    env = os.environ if env is None else env
    problems = []
    rc, out = git_fn("status", "--porcelain")
    if rc != 0:
        problems.append("git status failed")
    elif out:
        problems.append("the working tree is not clean (commit or stash everything first)")
    rc_tag, tag_sha = git_fn("rev-parse", "-q", "--verify", f"refs/tags/{TAG}^{{commit}}")
    rc_head, head = git_fn("rev-parse", "HEAD")
    if rc_tag != 0 or not tag_sha:
        problems.append(f"the git tag {TAG} does not exist (git tag {TAG} on the commit you are freezing)")
    elif rc_head != 0 or tag_sha != head:
        problems.append(f"the git tag {TAG} is not on HEAD (the configuration is frozen at the tag; HEAD has moved)")
    reason = verify_fn()
    if reason:
        problems.append(f"scripts/verify_frozen.py: {reason}")
    if not env.get(BUDGET_VAR):
        problems.append(f"{BUDGET_VAR} is not set (set the total the final runs may spend)")
    return problems


def injection_done(system: str, results_dir: Path = REPO / "evals" / "results") -> bool:
    for path in results_dir.glob("*.json"):
        try:
            r = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if r.get("split") == "injection" and r.get("system") == system:
            return True
    return False


def plan(injection_done_fn=injection_done) -> list[tuple[str, list[str]]]:
    """(label, command) in the order they run."""
    steps = []
    for split in ("hard", "test"):
        for s in SYSTEMS:
            cmd = PY + ["evals.run", "--system", s, "--split", split]
            if split == "test":
                cmd.append("--final")
            if s in MODEL_SYSTEMS:
                cmd += ["--approved-over-30", "--yes"]
            steps.append((f"{s} on {split}", cmd))
    for s in SYSTEMS:
        if not injection_done_fn(s):
            steps.append((f"{s} on the injection slice", PY + ["evals.run", "--system", s, "--source", "injection", "--limit", "15"]))
    steps.append(("report", PY + ["evals.report"]))
    steps.append(("hard-set note", PY + ["evals.report", "--hard-set-note"]))
    return steps


def estimates() -> list[str]:
    """One estimate line per model run, from the rules run offline and measured usage. Reads the hard and test records through the harness guards."""
    from agent.repair.config import Prices, load_routing, model_from_env
    from agent.repair.estimate import estimate_agent, estimate_llm_only_run
    from agent.rules.engine import RulesEngine
    from evals import guards
    lines, engine, routing = [], RulesEngine(), load_routing()
    for split in ("hard", "test"):
        recs = guards.load_records(guards.check_split(split, final=(split == "test")))
        items = [(r["id"], r["raw_lines"], r.get("country_hint")) for r in recs]
        lines.append(f"{split} / rules_only: $0 (no model)")
        lines.append(f"{split} / llm_only: {json.dumps(estimate_llm_only_run(len(recs), Prices.load(), model_from_env()))}")
        lines.append(f"{split} / agent:    {json.dumps(estimate_agent(items, engine, routing))}")
    lines.append("injection slice: 15 cases per model system, a few cents each")
    return lines


def main(argv=None, env=None, runner=None, input_fn=input, git_fn=git, verify_fn=verify_frozen, estimates_fn=estimates, out=print) -> int:
    runner = runner or (lambda cmd: subprocess.run(cmd, cwd=REPO).returncode)
    problems = preflight(env, git_fn, verify_fn)
    if problems:
        out("REFUSED: the final run cannot start:")
        for p in problems:
            out(f"  - {p}")
        return 2
    try:
        for line in estimates_fn():
            out(line)
    except Exception as e:     # the guards refuse the test split until it is enabled; say so plainly
        out(f"REFUSED: could not prepare the estimates: {e}")
        return 2
    steps = plan()
    out("\nThe runs, in order:")
    for label, cmd in steps:
        out(f"  {label}: {' '.join(cmd[2:])}")
    out("\nThis uses the frozen configuration, runs the hard set and the test split ONCE, and spends real money.")
    if input_fn("Type FINAL to start: ").strip() != "FINAL":
        out("REFUSED: FINAL was not typed. Nothing was run.")
        return 2
    for label, cmd in steps:
        out(f"\n=== {label}")
        rc = runner(cmd)
        if rc != 0:
            out(f"STOPPED: '{label}' exited with {rc}. Nothing after it was run. (If the test guard refused, check TEST_RUN_ENABLED in evals/guards.py and the frozen hash.)")
            return rc
    out("\nThe final runs are done. Review docs/eval-results.md; any change from here must be logged in docs/results-changelog.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
