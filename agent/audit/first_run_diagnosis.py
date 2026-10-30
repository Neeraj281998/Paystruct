"""python -m agent.audit.first_run_diagnosis [run_record.json]

Diagnoses a dev run of the agent with no API call: which records are wrong, what the rules produced for them, and what the
verifier would have said about the candidates in question. Dev only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from agent.repair.config import load_routing
from agent.repair.pipeline import RepairPipeline, compute_confidence
from agent.repair.store import InMemoryRepository
from agent.repair.validator import Candidate
from agent.rules.cli import load_split
from agent.rules.engine import RulesEngine
from agent.rules.scoring import score_record
from agent.rules.xsd import REPO_ROOT


def main(path: str | None = None) -> None:
    rec_path = Path(path) if path else next((REPO_ROOT / "evals" / "results").glob("*_agent_dev_first30_*.json"))
    run = json.loads(rec_path.read_text())
    n = run["n_records"]
    records = load_split("dev")[:n]
    engine = RulesEngine()
    pipe = RepairPipeline(engine, None, InMemoryRepository(), load_routing())
    routing = load_routing()
    print(f"run {rec_path.name}: n={n} exact_all={run['metrics']['exact_all']['k']} failure patterns={run['metrics']['failure_patterns']} "
          f"cost=${run['metrics']['cost_usd_total']}")
    if "records" in run:
        wrong = [r for r in run["records"] if not r["exact"]]
        print(f"the record keeps per-record details: {len(wrong)} wrong records")
    else:
        print("this run record has no per-record details; reconstructing from the rules (the records the model saw are the rules NEEDS_LLM ones)")
    for rec in records:
        rules = engine.parse(rec["raw_lines"], rec.get("country_hint"))
        if rules.route == "ACCEPT":
            continue
        print("\n" + "=" * 100)
        print(rec["id"], rec["difficulty"], rec["tags"], "hint:", rec.get("country_hint"))
        print("raw lines:", rec["raw_lines"])
        print("gold:     ", rec["gold"])
        print("rules:    ", rules.fields)
        print("rules route:", rules.route, rules.route_reasons, "confidence", rules.confidence, "how set:", {k: v for k, v in rules.field_basis.items() if v != "explicit"})
        print("rules vs gold:", score_record(rules.fields, rec["gold"], rec["country"]).pattern())
        for label, fields in (("rules output kept as is", dict(rules.fields)),
                              ("rules output without the elimination fields", {k: v for k, v in rules.fields.items() if rules.field_basis.get(k) != "elimination"})):
            cand = Candidate(fields)
            hard, unsupported, unchecked = pipe.verify(cand, rec["raw_lines"], rec.get("country_hint"), rules)
            sc = score_record(fields, rec["gold"], rec["country"])
            conf = {a: compute_confidence(fields, rules, a, 0.9, [] if not unsupported else unsupported, unchecked, routing) for a in (1, 2, 3)}
            print(f"\n  candidate = {label}: {fields}")
            print(f"    vs gold: {sc.pattern()}   hard reasons: {hard}   unsupported: {unsupported}   unchecked: {unchecked}")
            print(f"    confidence by attempt (model says 0.9): {conf}  threshold {routing['threshold']}  -> "
                  f"{'REPAIRED' if not hard and not unsupported and conf[1] >= routing['threshold'] else 'not repaired at attempt 1'}")


def skips() -> None:
    """Which dev records the model would see after fix 5 (elimination-only records are routed to REVIEW without a model call)."""
    import collections
    engine = RulesEngine()
    pipe = RepairPipeline(engine, object(), InMemoryRepository(), load_routing())
    counts: collections.Counter = collections.Counter()
    for rec in load_split("dev"):
        rules = engine.parse(rec["raw_lines"], rec.get("country_hint"))
        if rules.route == "NEEDS_LLM":
            counts["skipped: only unsupported elimination fields" if pipe._only_unsupported_elimination(rules) else "model called"] += 1
        else:
            counts[f"rules {rules.route}: no model call"] += 1
    for k, v in sorted(counts.items()):
        print(f"{v:5d}  {k}")


if __name__ == "__main__":
    if "--skips" in sys.argv:
        skips()
    else:
        main(next((a for a in sys.argv[1:] if not a.startswith("--")), None))
