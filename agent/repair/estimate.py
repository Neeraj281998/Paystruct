"""Cost estimates for real runs, from measured usage and a free offline pass of the rules. Nothing here calls the API.

The rules run first (free): the records the model would never see (rules ACCEPT, rules REVIEW, and the records fix 5 skips) cost nothing.
The cost of a record that does reach the model is MEASURED from an earlier agent run record (cost divided by the number of records
that made a model call), not typed in. With no such run record the expected cost is unknown and only the per-payment cap bounds the run.
"""
from __future__ import annotations

import json
from pathlib import Path

from agent.repair.config import Prices, run_budget_usd
from agent.repair.pipeline import RepairPipeline
from agent.repair.store import InMemoryRepository
from agent.rules.engine import RulesEngine
from agent.rules.xsd import REPO_ROOT

RESULTS_DIR = REPO_ROOT / "evals" / "results"
WORST_CASE_ATTEMPTS = 3          # the attempt cap: a record that fails every attempt costs about 3 times a typical one
# llm_only (not built yet) makes one call per record with no tools and no rules summary, so its prompt is shorter than the agent's.
# This ratio is an ASSUMPTION, stated here and printed with every llm_only estimate; replace it with a measurement once llm_only has run.
LLM_ONLY_PROMPT_RATIO = 0.5


def measured_usage(results_dir: Path = RESULTS_DIR) -> dict | None:
    """Usage per model-handled record and per API call, read from the agent run record with the most model-handled records."""
    best = None
    for path in sorted(Path(results_dir).glob("*.json")):
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if run.get("system") != "agent" or "records" not in run:
            continue
        handled = [r for r in run["records"] if any(s["tool"] == "llm_call" for s in r["system_extra"].get("steps", []))]
        if not handled:
            continue
        calls = [s for r in handled for s in r["system_extra"]["steps"] if s["tool"] == "llm_call"]
        cost = sum(r["cost_usd"] for r in handled)
        usage = {"file": path.name, "model": run["config"].get("model"), "model_handled_records": len(handled), "api_calls": len(calls),
                 "cost_usd": cost, "per_record_usd": cost / len(handled), "per_call_usd": cost / len(calls),
                 "tokens_in_per_call": sum(s["tokens_in"] for s in calls) / len(calls),
                 "tokens_out_per_call": sum(s["tokens_out"] for s in calls) / len(calls)}
        if best is None or usage["model_handled_records"] >= best["model_handled_records"]:
            best = usage
    return best


def measured_llm_only_usage(results_dir: Path = RESULTS_DIR) -> dict | None:
    """Cost per call of llm_only (one call per record), from the llm_only run record with the most calls that kept per-record details."""
    best = None
    for path in sorted(Path(results_dir).glob("*.json")):
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if run.get("system") != "llm_only" or "records" not in run:
            continue
        called = [r for r in run["records"] if (r["system_extra"].get("tokens_in") or 0) > 0]
        if not called:
            continue
        cost = sum(r["cost_usd"] for r in called)
        usage = {"file": path.name, "calls": len(called), "per_call_usd": cost / len(called),
                 "tokens_in_per_call": sum(r["system_extra"]["tokens_in"] for r in called) / len(called),
                 "tokens_out_per_call": sum(r["system_extra"]["tokens_out"] for r in called) / len(called)}
        if best is None or usage["calls"] >= best["calls"]:
            best = usage
    return best


def count_reaching_model(items, engine: RulesEngine, routing: dict) -> int:
    """How many of (msg_id, lines, hint) the model would see: rules NEEDS_LLM and not skipped by fix 5. Free."""
    pipe = RepairPipeline(engine, object(), InMemoryRepository(), routing)
    return sum(1 for _, lines, hint in items if pipe.reaches_model(engine.parse(lines, hint)))


def estimate_agent(items, engine: RulesEngine, routing: dict, results_dir: Path = RESULTS_DIR) -> dict:
    n = len(items)
    reach = count_reaching_model(items, engine, routing)
    usage = measured_usage(results_dir)
    cap = float(routing["max_cost_usd_per_payment"])
    out = {"records": n, "would_reach_the_model": reach, "per_payment_cap_usd": cap, "run_budget_usd": run_budget_usd()}
    if usage is None:
        out.update(expected_usd=None, worst_case_usd=round(reach * cap, 4),
                   note="no earlier agent run record to measure from: only the per-payment cap bounds this run")
        return out
    per = usage["per_record_usd"]
    out.update(expected_usd=round(reach * per, 4), worst_case_usd=round(reach * min(WORST_CASE_ATTEMPTS * per, cap), 4),
               per_model_record_usd=round(per, 5), measured_from=usage["file"], measured_on_records=usage["model_handled_records"])
    return out


def estimate_llm_only(n_records: int, usage: dict | None, prices: Prices, model: str, ratio: float = LLM_ONLY_PROMPT_RATIO) -> dict:
    """An ESTIMATE for llm_only: one call per record, the measured average output and a prompt `ratio` times the measured average input."""
    if usage is None:
        return {"records": n_records, "expected_usd": None, "note": "no measured run record: cannot estimate"}
    per_call = prices.cost(model, int(usage["tokens_in_per_call"] * ratio), int(usage["tokens_out_per_call"]))
    return {"records": n_records, "calls": n_records, "expected_usd": round(n_records * per_call, 4), "per_call_usd": round(per_call, 6),
            "prompt_size_ratio": ratio, "measured_per_call_usd": round(usage["per_call_usd"], 6), "measured_from": usage["file"],
            "note": f"an estimate: the measured average call, with the prompt assumed {ratio:.0%} of the agent's"}


def estimate_llm_only_run(n_records: int, prices: Prices, model: str, results_dir: Path = RESULTS_DIR) -> dict:
    """The estimate printed before an llm_only run: measured from an earlier llm_only run record when one exists, otherwise the stated
    assumption (the agent's measured call with the prompt scaled by LLM_ONLY_PROMPT_RATIO), labelled as such."""
    own = measured_llm_only_usage(results_dir)
    if own is not None:
        per = own["per_call_usd"]
        return {"records": n_records, "calls": n_records, "expected_usd": round(n_records * per, 4), "worst_case_usd": round(n_records * per * 1.0, 4),
                "per_call_usd": round(per, 6), "basis": "measured", "measured_from": own["file"], "run_budget_usd": run_budget_usd()}
    est = estimate_llm_only(n_records, measured_usage(results_dir), prices, model)
    est.update(basis="stated assumption (no llm_only run record yet)", worst_case_usd=est.get("expected_usd"), run_budget_usd=run_budget_usd())
    return est
