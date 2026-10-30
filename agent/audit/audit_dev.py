"""Audit of the dev result (no engine changes): scorer sanity, deliberate breakage, hint dependence, gazetteer dependence.

python -m agent.audit.audit_dev [--calibration]
Reads dev only (through agent.rules.cli.load_split, which refuses every other split but calibration).
"""
from __future__ import annotations

import argparse
from collections import Counter

from agent.rules.cli import load_split
from agent.rules.engine import RulesEngine, load_config
from agent.rules.gazetteer import Gazetteer
from agent.rules.scoring import score_record


def run(records, engine, use_hint=True):
    exact = acc = acc_wrong = 0
    preds = []
    for r in records:
        res = engine.parse(r["raw_lines"], r.get("country_hint") if use_hint else None)
        sc = score_record(res.fields, r["gold"], r["country"])
        exact += sc.exact
        if res.route == "ACCEPT":
            acc += 1
            acc_wrong += not sc.exact
        preds.append(res.fields)
    n = len(records)
    return {"exact": 100 * exact / n, "accepted": acc, "accepted_wrong": acc_wrong}, preds


def without(rule_id):
    order = [r for r in load_config()["order"] if r != rule_id]
    return RulesEngine(order=order)


def main(split: str) -> None:
    records = load_split(split)
    base_engine = RulesEngine()
    base, preds = run(records, base_engine)
    print(f"split={split} n={len(records)}")
    print(f"baseline                          exact={base['exact']:6.2f}  accepted={base['accepted']}  accepted_wrong={base['accepted_wrong']}")
    if split != "dev":
        return
    # 1. scorer sanity: predictions against another record's gold
    n = len(records)
    shifted = sum(score_record(preds[i], records[(i + 1) % n]["gold"], records[(i + 1) % n]["country"]).exact for i in range(n))
    same = [i for i in range(n)]
    by_country: dict[str, list[int]] = {}
    for i, r in enumerate(records):
        by_country.setdefault(r["country"], []).append(i)
    shifted_same = 0
    for idxs in by_country.values():
        for k, i in enumerate(idxs):
            j = idxs[(k + 1) % len(idxs)]
            shifted_same += score_record(preds[i], records[j]["gold"], records[j]["country"]).exact
    print(f"\nscorer sanity (prediction i vs gold i+1):  any country exact={100*shifted/n:.2f}%   same country exact={100*shifted_same/n:.2f}%")
    # 2. deliberate breakage
    print("\ndeliberate breakage")
    for rid, label in (("postcode", "postcode rule disabled"), ("street", "street/number split disabled"), ("country", "country detection disabled"),
                       ("town", "town rule disabled"), ("region", "region rule disabled")):
        r, _ = run(records, without(rid))
        print(f"  {label:32} exact={r['exact']:6.2f}  accepted={r['accepted']}  accepted_wrong={r['accepted_wrong']}")
    # 3. what the engine gets from the record besides the text
    r, _ = run(records, base_engine, use_hint=False)
    print(f"\nwithout country_hint                exact={r['exact']:6.2f}  accepted={r['accepted']}  accepted_wrong={r['accepted_wrong']}")
    hinted = sum(1 for x in records if x.get("country_hint"))
    print(f"  records carrying a country_hint: {hinted}")
    r, _ = run(records, RulesEngine(gazetteer=Gazetteer()))
    print(f"empty gazetteer                     exact={r['exact']:6.2f}  accepted={r['accepted']}  accepted_wrong={r['accepted_wrong']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev")
    main(ap.parse_args().split)
