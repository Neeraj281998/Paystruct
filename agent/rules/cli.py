"""python -m agent.rules.cli --split dev

Runs the rules engine over a TUNING split and prints exact match, field accuracy and route shares by country and by tier.
Only dev and calibration are allowed: the frozen test split is run once, on Day 5, and the hard set is for Day 3.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict

from agent.rules.engine import RulesEngine
from agent.rules.scoring import score_record
from agent.rules.state import ACCEPT, NEEDS_LLM, REVIEW
from agent.rules.xsd import REPO_ROOT

ALLOWED = ("dev", "calibration")
FORBIDDEN = ("test", "hard")


def refuse(name: str) -> None:
    sys.stderr.write(
        "\n" + "!" * 78 + f"\nREFUSED: split '{name}'.\n"
        "The frozen test split is never read while tuning; it is run ONCE, for the final numbers.\n"
        "The hard set is for Day 3 and stays untouched until the project owner says so.\n"
        "Allowed splits: " + ", ".join(ALLOWED) + "\n" + "!" * 78 + "\n\n")
    raise SystemExit(2)


def load_split(name: str) -> list[dict]:
    if name in FORBIDDEN or name not in ALLOWED:
        refuse(name)
    path = REPO_ROOT / "data/splits" / f"{name}.jsonl"
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:5.1f}" if b else "  n/a"


def evaluate(records: list[dict], engine: RulesEngine) -> list[dict]:
    rows = []
    for r in records:
        res = engine.parse(r["raw_lines"], r.get("country_hint"))
        sc = score_record(res.fields, r["gold"], r["country"])
        rows.append({"rec": r, "res": res, "score": sc})
    return rows


def summarise(rows: list[dict], key) -> list[tuple]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[key(row)].append(row)
    table = []
    for k in sorted(groups):
        g = groups[k]
        n = len(g)
        exact = sum(r["score"].exact for r in g)
        matched = sum(len(r["score"].matched) for r in g)
        total = sum(r["score"].n_gold for r in g)
        routes = Counter(r["res"].route for r in g)
        acc = [r for r in g if r["res"].route == ACCEPT]
        false_acc = sum(not r["score"].exact for r in acc)
        table.append((k, n, exact, matched, total, routes, len(acc), false_acc))
    return table


def print_table(title: str, table: list[tuple]) -> None:
    print(f"\n{title}")
    print(f"{'':12}{'n':>5}{'exact%':>8}{'field%':>8}{'ACCEPT%':>9}{'LLM%':>7}{'REVIEW%':>9}{'accepted-wrong':>16}")
    for k, n, exact, matched, total, routes, acc, false_acc in table:
        print(f"{k:12}{n:5d}{pct(exact, n):>8}{pct(matched, total):>8}{pct(routes[ACCEPT], n):>9}{pct(routes[NEEDS_LLM], n):>7}"
              f"{pct(routes[REVIEW], n):>9}{false_acc:>8d}/{acc:<7d}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--split", required=True)
    ap.add_argument("--failures", type=int, default=0, help="print the N most common failure patterns")
    ap.add_argument("--examples", type=int, default=2, help="examples per failure pattern")
    ap.add_argument("--only", help="only this country code")
    args = ap.parse_args(argv)
    if args.split in FORBIDDEN or args.split not in ALLOWED:
        refuse(args.split)
    records = load_split(args.split)
    if args.only:
        records = [r for r in records if r["country"] == args.only]
    engine = RulesEngine()
    rows = evaluate(records, engine)
    print(f"split={args.split}  records={len(rows)}  (rules only, no LLM)")
    print_table("all", summarise(rows, lambda r: "ALL"))
    print_table("by country", summarise(rows, lambda r: r["rec"]["country"]))
    print_table("by tier", summarise(rows, lambda r: r["rec"]["difficulty"]))
    if args.failures:
        pats: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            if not r["score"].exact:
                pats[r["score"].pattern()].append(r)
        print(f"\ntop {args.failures} failure patterns ({sum(len(v) for v in pats.values())} failing records)")
        for p, g in sorted(pats.items(), key=lambda kv: -len(kv[1]))[: args.failures]:
            print(f"\n{len(g):4d}  {p}")
            for r in g[: args.examples]:
                print(f"      {r['rec']['id']} {r['res'].route} {r['rec']['raw_lines']}")
                print(f"        gold: { {k: v for k, v in r['rec']['gold'].items()} }")
                print(f"        pred: {r['res'].fields}  leftovers={[l.text for l in r['res'].leftovers]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
