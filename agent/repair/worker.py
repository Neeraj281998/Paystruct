"""python -m agent.repair.worker --source dev --limit 30

Reads queued items (a JSONL split or the agent_queue table), claims each msg_id by inserting it as in_progress, runs the
pipeline, stores the result and the steps, and commits only after the result is stored. A duplicate delivery is skipped.

Real API runs: --limit is mandatory; a run budget (PAYSTRUCT_RUN_BUDGET_USD, default 2.00) aborts the run when reached; an estimate
is printed first and --yes is needed for more than 50 records; more than 30 records need --approved-over-30 (a session rule).
--no-llm runs the rules and the verifier only: no key, no network.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from agent.repair.agent import RepairAgent, make_client
from agent.repair.config import Prices, load_routing, model_from_env, run_budget_usd
from agent.repair.pipeline import RepairPipeline
from agent.repair.store import InMemoryRepository
from agent.rules.engine import RulesEngine
from agent.rules.xsd import REPO_ROOT

# Day 4 may run the agent on dev only. The calibration split, the hard set and the test split are Day 5.
ALLOWED_SPLITS = ("dev",)
UNAPPROVED_REAL_API_RECORDS = 30
CONFIRM_ABOVE = 50
EST_TOKENS_IN, EST_TOKENS_OUT, EST_ATTEMPTS = 3000, 400, 1.3


def estimate(n: int, model: str, prices: Prices, routing: dict) -> dict:
    per = prices.cost(model, EST_TOKENS_IN, EST_TOKENS_OUT) * EST_ATTEMPTS
    return {"records": n, "typical_if_all_need_the_model": round(n * per, 4), "hard_cap_per_payment": routing["max_cost_usd_per_payment"],
            "hard_cap_total": round(n * routing["max_cost_usd_per_payment"], 4), "run_budget": run_budget_usd()}


def load_jsonl(split: str, limit: int) -> list[tuple[str, list[str], str | None]]:
    if split not in ALLOWED_SPLITS:
        raise SystemExit(f"REFUSED: the agent runs on {', '.join(ALLOWED_SPLITS)} only today (the other splits are Day 5)")
    path = REPO_ROOT / "data" / "splits" / f"{split}.jsonl"
    out = []
    for line in path.read_text(encoding="utf-8").splitlines()[:limit]:
        r = json.loads(line)
        out.append((r["id"], r["raw_lines"], r.get("country_hint")))
    return out


def load_queue(conn, limit: int) -> list[tuple[str, list[str], str | None]]:
    rows = conn.execute("SELECT msg_id, raw_lines, country_hint FROM agent_queue ORDER BY enqueued_at LIMIT %s", (limit,)).fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


def build_pipeline(repo, client=None, use_llm: bool = True, routing: dict | None = None, engine: RulesEngine | None = None) -> RepairPipeline:
    routing = routing or load_routing()
    engine = engine or RulesEngine()
    agent = None
    if use_llm:
        client = client or make_client(float(routing["request_timeout_s"]))
        agent = RepairAgent(client, engine, model_from_env(), routing, Prices.load())
    return RepairPipeline(engine, agent, repo, routing)


def run(items, pipeline: RepairPipeline, budget_usd: float, log=print) -> dict:
    total, done, stats = 0.0, 0, {"repaired": 0, "review": 0, "retry_later": 0, "skipped": 0}
    for msg_id, lines, hint in items:
        if total >= budget_usd:
            log(f"run budget of ${budget_usd:.2f} reached after {done} records: stopping")
            break
        out = pipeline.process(msg_id, lines, hint)
        total += out.cost_usd
        done += 1
        stats[out.status] = stats.get(out.status, 0) + 1
    return {"processed": done, "cost_usd": round(total, 6), **stats}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", choices=["dev", "queue"], default="dev")
    ap.add_argument("--limit", type=int, required=True)
    ap.add_argument("--yes", action="store_true", help=f"required for more than {CONFIRM_ABOVE} records")
    ap.add_argument("--approved-over-30", action="store_true", help="the project owner approved a real API run of more than 30 records")
    ap.add_argument("--no-llm", action="store_true", help="rules and verifier only: no key, no network")
    ap.add_argument("--memory", action="store_true", help="keep results in memory instead of PostgreSQL")
    args = ap.parse_args(argv)
    if args.limit < 1:
        sys.stderr.write("--limit must be at least 1\n")
        return 2
    routing, prices, model = load_routing(), Prices.load(), model_from_env()
    use_llm = not args.no_llm
    if use_llm:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            sys.stderr.write("ANTHROPIC_API_KEY is not set (it is read from the environment only). Use --no-llm to run without a model.\n")
            return 2
        if args.limit > UNAPPROVED_REAL_API_RECORDS and not args.approved_over_30:
            sys.stderr.write(f"REFUSED: more than {UNAPPROVED_REAL_API_RECORDS} records against the real API needs the owner's approval (--approved-over-30)\n")
            return 2
        est = estimate(args.limit, model, prices, routing)
        print(f"model {model}; estimate: {json.dumps(est)}")
        if args.limit > CONFIRM_ABOVE and not args.yes:
            sys.stderr.write(f"REFUSED: more than {CONFIRM_ABOVE} records need --yes after you have read the estimate above\n")
            return 2
    conn = None
    if args.memory:
        repo = InMemoryRepository(routing["max_payment_tries"], routing["lease_seconds"])
    else:
        from agent.db import connection
        from agent.repair.store import PostgresRepository
        conn = connection.connect()
        connection.apply_schema(conn)
        repo = PostgresRepository(conn, routing["max_payment_tries"], routing["lease_seconds"])
    items = load_queue(conn, args.limit) if args.source == "queue" else load_jsonl(args.source, args.limit)
    pipeline = build_pipeline(repo, use_llm=use_llm, routing=routing)
    result = run(items, pipeline, run_budget_usd())
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
