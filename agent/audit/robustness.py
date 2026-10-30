"""python -m agent.audit.robustness : run the engine on the 30 audit addresses and compare with my expected fields."""
from agent.audit.robustness_cases import CASES
from agent.rules.engine import RulesEngine
from agent.rules.scoring import score_record

engine = RulesEngine()
wrong = accepted_wrong = 0
for cid, lines, expected, note in CASES:
    res = engine.parse(lines)
    sc = score_record(res.fields, expected, expected["Ctry"])
    wrong += not sc.exact
    flag = "OK   " if sc.exact else "WRONG"
    if not sc.exact and res.route == "ACCEPT":
        accepted_wrong += 1
    print(f"{flag} {cid:5} {res.route:10} conf={res.confidence:.2f}  {note}")
    print(f"      in  : {lines}")
    if not sc.exact:
        print(f"      want: { {k: v for k, v in expected.items()} }")
    print(f"      got : {res.fields}")
    if res.leftovers:
        print(f"      left: {[l.text for l in res.leftovers]}  reasons={res.route_reasons}")
print(f"\nexact: {len(CASES) - wrong}/{len(CASES)}   wrong: {wrong}   wrong AND accepted: {accepted_wrong}")
