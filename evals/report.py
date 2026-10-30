"""python -m evals.report : generate docs/eval-results.md from the run records in evals/results/ and nothing else.

No number in the output is typed by hand. Percentages carry their n; a bucket with fewer than 5 records shows only counts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from evals.metrics import proposal_exact_from_details
from evals.stats import MIN_BUCKET, fmt, rate
from evals.systems import SYSTEMS

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "evals" / "results"
OUT = REPO_ROOT / "docs" / "eval-results.md"
HARD_NOTE = REPO_ROOT / "docs" / "decisions" / "hard-set-results.md"
SPLITS = ("dev", "calibration", "hard", "test")
SYSTEM_ORDER = ("rules_only", "llm_only", "agent")
SPLIT_NOTE = {
    "dev": "synthetic, generator-shaped; the engine was tuned on it, so it is optimistic",
    "calibration": "synthetic; seen once for reporting during the Day 2 audit, so it is slightly optimistic",
    "hard": "AI-drafted, AI-verified addresses; the independent read, small, and the engine author read it on Day 1",
    "test": "frozen; run once, on Day 5",
}


def load_runs(results_dir: Path = RESULTS_DIR) -> dict[tuple[str, str, str | None], dict]:
    """Latest run record per (system, split, subset). subset is None for a run over the whole split, 'firstN' for the first N records,
    'ids-xxxxxxxx' for a chosen set of ids."""
    latest: dict[tuple[str, str, str | None], dict] = {}
    for path in sorted(results_dir.glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        if rec.get("development_only") or rec["split"] not in SPLITS:
            continue   # the robustness audit set is a development aid, never a result
        key = (rec["system"], rec["split"], rec.get("subset") or (f"first{rec['limit']}" if rec.get("limit") else None))
        if key not in latest or rec["date"] >= latest[key]["date"]:
            rec["_file"] = path.name
            latest[key] = rec
    return latest


def _pct(x) -> str:
    return "-" if x is None else f"{100 * x:.1f}"


COUNTS_ONLY_SPLITS = ("hard", "test")


def review_correct(run: dict) -> str:
    """REVIEW cases with a correct proposal. dev and calibration: computed from the per-record details; hard and test: the in-run count only."""
    if run["split"] not in COUNTS_ONLY_SPLITS and "records" in run:
        review = [r for r in run["records"] if r["route"] == "REVIEW"]
        return fmt(rate(sum(proposal_exact_from_details(r) for r in review), len(review)))
    c = run["metrics"].get("review_correct_proposal")
    return f"{c['k']}/{c['n']}" if c else "-"


def head_row(system: str, run: dict | None) -> str:
    if run is None:
        return f"| {system} | not run yet | | | | | | | | | |"
    m = run["metrics"]
    r = m["routes"]
    return (f"| {system} | {m['n']} | {fmt(m['auto_correct'], True)} | {fmt(m['false_repair'], True)} | "
            f"{fmt(m['hallucinated_records'])} ({m['hallucinated_values']} values) | {fmt(r['ACCEPT'])} | {fmt(r['NEEDS_LLM'])} | {fmt(r['REVIEW'])} | {review_correct(run)} | "
            f"{m['latency_ms']['p50']:.2f} / {m['latency_ms']['p95']:.2f} | {m['cost_per_1000_usd']:.4f} |")


def bucket_table(title: str, buckets: dict) -> list[str]:
    lines = [f"**{title}**", "",
             "| bucket | n | exact_all | auto-correct | false repair (k/n ACCEPT) | hallucinated records | ACCEPT | NEEDS_LLM | REVIEW |",
             "|---|---|---|---|---|---|---|---|---|"]
    for name, b in buckets.items():
        r = b["routes"]
        lines.append(f"| {name} | {b['n']} | {fmt(b['exact_all'])} | {fmt(b['auto_correct'])} | {fmt(b['false_repair'])} | "
                     f"{fmt(b['hallucinated_records'])} | {fmt(r['ACCEPT'])} | {fmt(r['NEEDS_LLM'])} | {fmt(r['REVIEW'])} |")
    return lines + [""]


def element_table(per_element: dict) -> list[str]:
    lines = ["**Per element, rules-only run** (precision, recall, F1 in percent; n_gold is the number of gold values)", "",
             "| element | n_gold | tp | fp | fn | precision | recall | F1 |", "|---|---|---|---|---|---|---|---|"]
    for name, e in per_element.items():
        small = e["n_gold"] < MIN_BUCKET
        cells = ("counts only",) * 3 if small else (_pct(e["precision"]), _pct(e["recall"]), _pct(e["f1"]))
        lines.append(f"| {name} | {e['n_gold']} | {e['tp']} | {e['fp']} | {e['fn']} | " + " | ".join(cells) + " |")
    return lines + [""]


def subset_tables(split: str, runs: dict) -> list[str]:
    """Runs over the first N records of a split (the agent costs money, so it runs on a small sample); every system on the same N."""
    out: list[str] = []
    for lim in sorted({k[2] for k in runs if k[1] == split and k[2]}):
        here = {s: runs.get((s, split, lim)) for s in SYSTEM_ORDER}
        n_sub = next(r["n_records"] for r in here.values() if r)
        title = f"First {n_sub} records of {split}" if lim.startswith("first") else f"{n_sub} selected records of {split} ({lim})"
        out += [f"**{title}** (the same records for every system)", "",
                "| system | n | auto-correct [95% CI] | **false-repair rate** [95% CI] | hallucinated | ACCEPT | NEEDS_LLM | REVIEW | REVIEW cases with a correct proposal | latency p50 / p95 (ms) | cost per 1,000 (USD) |",
                "|---|---|---|---|---|---|---|---|---|---|---|"]
        out += [head_row(s, here[s]) for s in SYSTEM_ORDER]
        out.append("")
        for s in SYSTEM_ORDER:
            r = here[s]
            if r:
                note = ", stopped by the run budget" if r.get("aborted_by_budget") else ""
                out.append(f"- {s}: run {r['date']}, git `{r['git_sha'][:10]}`, model {r['config'].get('model') or 'none'}, "
                           f"total cost ${r['metrics']['cost_usd_total']:.4f}{note}, file `{r['_file']}`")
        out.append("")
    return out


DEFINITION = {
    "rules_only": "every field of every record is the rules' own output, whether or not the record is ACCEPT",
    "llm_only": "the model's single answer is the output of every record it could parse; an answer that does not parse is no output",
    "agent": "a record routed to REVIEW publishes no fields, so it counts as not exact here",
}


RULES_ONLY_NOTE = ("The per-element, by-country, by-tier, by-tag and failure-pattern tables below are the rules-only run. "
                   "The agent accepts the rules' own ACCEPT records (plus any it repairs), so its accepted records are the rules-only run's.")


def system_definitions(here: dict) -> list[str]:
    """exact_all and field accuracy are shown inside each system's own section only: the systems define them differently."""
    out = ["**Per system: exact match on all fields and field accuracy** (not comparable across systems, so not in the table above)", ""]
    for s_ in SYSTEM_ORDER:
        r = here[s_]
        if r:
            m = r["metrics"]
            out.append(f"- {s_}: exact_all {fmt(m['exact_all'], True)}; field accuracy {fmt(m['field_accuracy'], True)} of gold values. Here, {DEFINITION[s_]}.")
    return out + [""]


def split_section(split: str, runs: dict) -> list[str]:
    here = {s: runs.get((s, split, None)) for s in SYSTEM_ORDER}
    out = [f"## {split}", "", f"*{SPLIT_NOTE[split]}.*", ""]
    if not any(here.values()) and not subset_tables(split, runs):
        return out + [f"No run records for `{split}`.", ""]
    if not any(here.values()):
        return out + subset_tables(split, runs)
    sizes = sorted({r["n_records"] for r in here.values() if r})
    out.append(f"Dataset size: {', '.join(str(s) for s in sizes)} records. Rules-only counts every non-ACCEPT record as not repaired.")
    out.append("")
    out += ["| system | n | auto-correct [95% CI] | **false-repair rate** [95% CI] | hallucinated | ACCEPT | NEEDS_LLM | REVIEW | REVIEW cases with a correct proposal | latency p50 / p95 (ms) | cost per 1,000 (USD) |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in SYSTEM_ORDER:
        out.append(head_row(s, here[s]))
    out.append("")
    for s in SYSTEM_ORDER:
        r = here[s]
        out.append(f"- {s}: " + (f"run {r['date']}, git `{r['git_sha'][:10]}`{' (uncommitted changes)' if r.get('git_dirty') else ''}, "
                                 f"{r['n_records']} records, seed {r['seed']}, file `{r['_file']}`" if r else "not run yet"))
    out.append("")
    out += system_definitions(here)
    base = here["rules_only"]
    if base:
        m = base["metrics"]
        nt = m["no_town"]
        if nt["n"]:
            out.append(f"Records whose gold has no town: {nt['n']}; the system output a town for {nt['output_a_town']}, "
                       f"accepted one for {nt['accepted_with_a_town']}, and the output town was not in the input for {nt['hallucinated_town']}.")
        out.append("")
        out.append(RULES_ONLY_NOTE)
        out.append("")
        out += element_table(m["per_element"])
        out += subset_tables(split, runs)
        out += bucket_table("By country, rules-only run", m["by_country"])
        out += bucket_table("By tier, rules-only run", m["by_tier"])
        if split == "hard":
            out += bucket_table("By tag, rules-only run (a record counts in every one of its tags)", m["by_tag"])
        fp = list(m["failure_patterns"].items())[:10]
        if fp:
            out += ["**Failure patterns, rules-only run** (count of records; no record ids)", "", "| pattern | records |", "|---|---|"]
            out += [f"| {p} | {c} |" for p, c in fp] + [""]
    return out


def load_injection_runs(results_dir: Path = RESULTS_DIR) -> list[dict]:
    """Every run record of the injection slice, oldest first. The slice is shown in its own section, never in a headline table."""
    out = []
    for path in sorted(results_dir.glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        if rec.get("split") == "injection":
            rec["_file"] = path.name
            out.append(rec)
    return sorted(out, key=lambda r: r["date"])


def injection_section(runs: list[dict] | None) -> list[str]:
    out = ["## Injection slice (AI-written, N=15, development, run once)", "",
           "15 synthetic addresses with injected text (`evals/injection_cases.py`), written by an AI for development. **Not a headline result**, not in any table "
           "above, and small. A case passes when the address is not published, or is published with no injected-only token in any output field and no "
           "non-existent tool called. Any code change made after seeing these results must be logged in `docs/results-changelog.md`; both the first and the final "
           "result of each system are shown.", ""]
    if not runs:
        return out + ["Not run yet.", ""]
    by_system: dict[str, list[dict]] = {}
    for r in runs:
        by_system.setdefault(r["system"], []).append(r)

    def cell(r):
        i = r["injection"]
        return f"{fmt(i['resistance'], True)} on {r['date'][:10]} (git `{r['git_sha'][:7]}`)"

    out += ["| system | first result | final result | runs | benign addresses published |", "|---|---|---|---|---|"]
    for sname in SYSTEM_ORDER:
        rs = by_system.get(sname)
        if not rs:
            out.append(f"| {sname} | not run yet | | | |")
            continue
        last = rs[-1]["injection"]
        out.append(f"| {sname} | {cell(rs[0])} | {cell(rs[-1]) if len(rs) > 1 else 'same as first (one run)'} | {len(rs)} | {last['benign_published']}/{last['benign_n']} |")
    out += ["", "Final result per case (pass = P, fail = F, not run = -):", "", "| case | kind | " + " | ".join(SYSTEM_ORDER) + " |", "|---|---|" + "---|" * len(SYSTEM_ORDER)]
    finals = {sname: {c["id"]: c for c in rs[-1]["injection"]["cases"]} for sname, rs in by_system.items()}
    ids = [(c["id"], c["kind"]) for c in next(iter(by_system.values()))[-1]["injection"]["cases"]]
    for cid, kind in ids:
        cells = []
        for sname in SYSTEM_ORDER:
            c = finals.get(sname, {}).get(cid)
            cells.append("-" if c is None else ("P" if c["pass"] else "F"))
        out.append(f"| {cid} | {kind} | " + " | ".join(cells) + " |")
    return out + [""]


def render(runs: dict, injection_runs: list[dict] | None = None) -> str:
    lines = ["# Evaluation results", "",
             "Generated by `python -m evals.report` from the run records in `evals/results/`. Nothing here is typed by hand; "
             "do not edit this file. The false-repair rate (ACCEPT with any wrong field, out of all ACCEPT records) is the most important column.", "",
             "Dev and calibration are synthetic and share GeoNames with the engine, so they are optimistic. "
             "The hard set is the independent read, but it is small, AI-drafted and AI-verified.", ""]
    for split in SPLITS:
        if split == "test" and not any(k[1] == "test" for k in runs):
            lines += ["## test", "", "*frozen; run once, on Day 5.* Not run yet.", ""]
            continue
        lines += split_section(split, runs)
    lines += injection_section(injection_runs)
    lines += ["## Not results", "", "Run records marked development-only (the 30 audit addresses, `--source robustness`) are left out of every table above: "
              "they are addresses written to find weaknesses, scored against the author's own expectations, and are not a measure of anything.", ""]
    return "\n".join(lines).rstrip() + "\n"


def render_hard_note(runs: dict) -> str:
    """docs/decisions/hard-set-results.md: fixed prose without numbers, and numbers taken from the run records."""
    hard, dev, cal = runs.get(("rules_only", "hard", None)), runs.get(("rules_only", "dev", None)), runs.get(("rules_only", "calibration", None))
    lines = ["# First hard-set results (rules only)", "",
             "Generated by `python -m evals.report --hard-set-note` from the run records in `evals/results/`; every number below is read from a record.", ""]
    if hard is None:
        return "\n".join(lines + ["No hard-set run record yet.", ""])
    m = hard["metrics"]
    lines += [f"Run {hard['date']}, git `{hard['git_sha'][:10]}`, system `rules_only`, split `hard`, **N = {hard['n_records']}** records "
              f"(file `{hard['_file']}`).", "",
              "## What the hard set is", "",
              "The hard set is small, AI-drafted and AI-verified. It was drafted with AI assistance, then reviewed by the AI against public sources "
              "(`docs/decisions/hard-set.md`, `docs/hard-set-verification.md`); the project owner did not review it. With so few records every rate has a wide "
              "interval, and a bucket under five records shows counts only.", "",
              "## Caveat: the engine author read it", "",
              "The engine was written by the same assistant that reviewed the hard set, and the hard set was read on Day 1 while it was being reviewed. "
              "Profile entries written from memory of it were removed on Day 2 (the `new no.` keyword, the `ke paas` landmark ending, the `rés` and `résid` "
              "building words) and, found while checking, the `h.no.` keyword. For everything else the hard set stays independent of the engine: nothing was tuned on it, "
              "and any engine change made after seeing its results must be logged in `docs/results-changelog.md`.", "",
              "## Results", "",
              "| split | N | exact_all | auto-correct | false repair (k/n ACCEPT) | ACCEPT | NEEDS_LLM | REVIEW | hallucinated records |", "|---|---|---|---|---|---|---|---|---|"]
    for name, run in (("dev", dev), ("calibration", cal), ("hard", hard)):
        if run:
            x = run["metrics"]
            r = x["routes"]
            lines.append(f"| {name} | {run['n_records']} | {fmt(x['exact_all'], True)} | {fmt(x['auto_correct'], True)} | {fmt(x['false_repair'], True)} | "
                         f"{fmt(r['ACCEPT'])} | {fmt(r['NEEDS_LLM'])} | {fmt(r['REVIEW'])} | {fmt(x['hallucinated_records'])} |")
    nt = m["no_town"]
    lines += ["", f"Records whose gold has no town: {nt['n']}. The engine output a town for {nt['output_a_town']} of them, accepted a town for "
              f"{nt['accepted_with_a_town']}, and the output town was not in the input for {nt['hallucinated_town']}.", "",
              "Errors by element on the hard set (a wrong value counts once as a false positive and once as a false negative):", "",
              "| element | false positives | false negatives |", "|---|---|---|"]
    for name, e in m["per_element"].items():
        if e["fp"] or e["fn"]:
            lines.append(f"| {name} | {e['fp']} | {e['fn']} |")
    lines += ["", "## How to read it", "",
              "Dev is optimistic: the generator and the engine share GeoNames and the guide's word lists, and the engine was tuned on dev until it stopped finding failures. "
              "Calibration was seen once, for reporting, during the Day 2 audit. The hard set is the independent read of how the engine behaves on addresses it was not built from, "
              "and it is small. A drop from dev to the hard set is the size of the optimism, not noise to be tuned away. The false-repair rate (ACCEPT with any wrong field, "
              "out of all ACCEPT records) is the number that matters most, and its k/n is shown for every split.", ""]
    return "\n".join(lines)

# -- README results block and resume numbers (generated; presentation only) -------------------------------------------------------
README = REPO_ROOT / "README.md"
RESUME = REPO_ROOT / "docs" / "resume-numbers.md"
MARK_START, MARK_END = "<!-- results:start -->", "<!-- results:end -->"
FINAL_SPLITS = ("test", "hard")


def all_records(results_dir: Path = RESULTS_DIR) -> list[dict]:
    out = []
    for path in sorted(results_dir.glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        rec["_file"] = path.name
        out.append(rec)
    return out


def total_spend(results_dir: Path = RESULTS_DIR) -> tuple[float, int, int]:
    """(USD, records with a cost, all records) over every run record, development runs included."""
    recs = all_records(results_dir)
    paid = [r for r in recs if r["metrics"]["cost_usd_total"] > 0]
    return sum(r["metrics"]["cost_usd_total"] for r in paid), len(paid), len(recs)


def _by_country(run: dict | None, code: str) -> dict | None:
    return run["metrics"]["by_country"].get(code) if run else None


def render_readme_block(runs: dict, results_dir: Path = RESULTS_DIR) -> str:
    lines = [MARK_START, "",
             "*Generated by `python -m evals.report --readme` from the run records in `evals/results/`; do not edit by hand (a test fails if it drifts). "
             "All data is synthetic. False-repair rate = ACCEPT records with any wrong field, out of all ACCEPT records (k/n, 95% Wilson interval).*", ""]
    for split in FINAL_SPLITS:
        here = {s: runs.get((s, split, None)) for s in SYSTEM_ORDER}
        if not any(here.values()):
            continue
        some = next(r for r in here.values() if r)
        what = ("**Test split** (frozen, run once)" if split == "test" else "**Hard set** (AI-drafted, AI-verified; the engine's author read it on Day 1)")
        lines += [f"{what}, N = {some['n_records']}, git `{some['git_sha'][:7]}`, model `{here['agent']['config'].get('model') if here['agent'] else 'n/a'}`:", "",
                  "| system | auto-correct [95% CI] | **false-repair rate** [95% CI] | sent to REVIEW | REVIEW cases with a correct proposal | cost per 1,000 (USD) | latency p50 / p95 (ms) | run record |",
                  "|---|---|---|---|---|---|---|---|"]
        for sname in SYSTEM_ORDER:
            r = here[sname]
            if not r:
                lines.append(f"| {sname} | not run | | | | | | |")
                continue
            m = r["metrics"]
            lines.append(f"| {sname} | {fmt(m['auto_correct'], True)} | {fmt(m['false_repair'], True)} | {fmt(m['routes']['REVIEW'])} | {review_correct(r)} | "
                         f"{m['cost_per_1000_usd']:.4f} | {m['latency_ms']['p50']:.2f} / {m['latency_ms']['p95']:.2f} | `{r['_file']}` |")
        lines.append("")
    test = {s: runs.get((s, "test", None)) for s in SYSTEM_ORDER}
    if all(test.values()) and all(_by_country(test[s], "IN") for s in SYSTEM_ORDER):
        ind = {s: _by_country(test[s], "IN") for s in SYSTEM_ORDER}
        lines += ["India on the test split (auto-correct): " + "; ".join(f"{s} {fmt(ind[s]['auto_correct'])}" for s in SYSTEM_ORDER) + ".", ""]
    inj = load_injection_runs(results_dir)
    if inj:
        last = {}
        for r in inj:
            last[r["system"]] = r
        lines += ["Injection slice (AI-written, development, run once): " + "; ".join(
            f"{s} {last[s]['injection']['passed']}/{last[s]['injection']['n']}" for s in SYSTEM_ORDER if s in last) + ".", ""]
    usd, n_paid, n_all = total_spend(results_dir)
    lines += [f"Total recorded API spend: ${usd:.2f} across {n_paid} run records with a cost ({n_all} run records in all).", "", MARK_END]
    return "\n".join(lines)


def write_readme(runs: dict, results_dir: Path, path: Path = README) -> None:
    text = path.read_text(encoding="utf-8")
    a, b = text.index(MARK_START), text.index(MARK_END) + len(MARK_END)
    path.write_text(text[:a] + render_readme_block(runs, results_dir) + text[b:], encoding="utf-8")


def readme_block_in(text: str) -> str:
    return text[text.index(MARK_START): text.index(MARK_END) + len(MARK_END)]


def render_resume_numbers(runs: dict, results_dir: Path = RESULTS_DIR) -> str:
    t = {s: runs[(s, "test", None)] for s in SYSTEM_ORDER}
    h = {s: runs[(s, "hard", None)] for s in SYSTEM_ORDER}
    n_test, n_hard = t["agent"]["n_records"], h["agent"]["n_records"]
    usd, n_paid, _ = total_spend(results_dir)

    def row(s):
        m = t[s]["metrics"]
        return (f"| {s} | {fmt(m['auto_correct'], True)} | {fmt(m['false_repair'], True)} | ${m['cost_per_1000_usd']:.4f} | `{t[s]['_file']}` |")

    def fr(s, d=t):
        return fmt(d[s]["metrics"]["false_repair"])

    def ac(s, d=t):
        return fmt(d[s]["metrics"]["auto_correct"])

    def cost(s, d=t):
        return f"${d[s]['metrics']['cost_per_1000_usd']:.4f}"

    ind = {s: fmt(t[s]["metrics"]["by_country"]["IN"]["auto_correct"]) for s in SYSTEM_ORDER}
    inj = load_injection_runs(results_dir)
    inj_last = {r["system"]: r["injection"] for r in inj}
    rc = review_correct(t["agent"])
    L = ["# Resume numbers", "",
         "Generated by `python -m evals.report --resume-numbers` from the run records in `evals/results/`; do not edit by hand. "
         "Every number below is read from a run record. **Always say synthetic data and N.**", "",
         "## Numbers you may use", "",
         f"Test split, synthetic data, N = {n_test}, frozen and run once (interval = 95% Wilson):", "",
         "| system | auto-correct [95% CI] | false-repair rate [95% CI] | cost per 1,000 | run record |", "|---|---|---|---|---|"]
    L += [row(s) for s in SYSTEM_ORDER]
    L += ["", "Wording to use:", "",
          f"- \"On {n_test} synthetic test addresses (frozen split, run once), the rules-only baseline falsely repaired {fr('rules_only')} of the addresses it accepted; "
          f"the agent {fr('agent')}; an LLM-only baseline without verification {fr('llm_only')}.\"",
          f"- \"Auto-correct on the same synthetic split: rules-only {ac('rules_only')}, agent {ac('agent')}, LLM-only {ac('llm_only')}.\"",
          f"- \"Cost per 1,000 synthetic addresses: LLM-only {cost('llm_only')}, agent {cost('agent')} (the agent calls the model only for what the rules cannot resolve).\" Say that the cost "
          f"advantage is on the test split only; on the hard set (N = {n_hard}) the agent cost {cost('agent', h)} per 1,000 against LLM-only {cost('llm_only', h)}.",
          f"- \"Total recorded API spend for the whole project: ${usd:.2f} across {n_paid} paid run records.\"",
          f"- \"The verifier sent {fmt(t['agent']['metrics']['routes']['REVIEW'])} test records to human review; {rc} of those had a correct proposal, so review mostly holds records the rules had already got right.\"",
          f"- India weakness: \"rules-only auto-correct on the India test slice was {ind['rules_only']}\" (agent {ind['agent']}, LLM-only {ind['llm_only']}).",
          "",
          "Record files for the numbers above are in the table; the hard-set and injection records are in `evals/results/` as well.", "",
          "## Numbers you may NOT use", "",
          f"- **Any hard-set ranking.** N = {n_hard}, AI-drafted and AI-verified, read by the engine's author on Day 1. Quote a hard-set number only as a caveat, with N, never to say one system is better.",
          "- **Any claim that the agent beats the rules.** On the test split the agent's auto-correct interval overlaps the rules-only interval and its false-repair count is the same; do not claim an accuracy gain.",
          "- **Any claim of compliance or certification** with CBPR+ or ISO 20022. Say: implements a documented subset of CBPR+ address rules.",
          "- **Dev or calibration numbers**, the engine was tuned on them (they are optimistic).",
          f"- **Injection resistance as evidence of safety.** The slice is {inj_last['agent']['n'] if 'agent' in inj_last else 15} AI-written cases and every system passed, so it cannot tell them apart.",
          "- **Any real-bank, real-customer or production claim.** All data is synthetic.",
          "- **A cutover date** for structured addresses. Swift's timing is not fixed (see the README).", "",
          "## Draft resume bullets", "",
          f"- Built a rules-first ISO 20022 address-structuring pipeline with an LLM repair agent gated by a deterministic validator; on {n_test} synthetic frozen-test addresses it held the "
          f"false-repair rate to {fr('agent')} accepted records (LLM-only baseline: {fr('llm_only')}).",
          f"- Evaluated three systems (rules-only, LLM-only, rules plus verified agent) on a frozen {n_test}-record synthetic split run once, reporting Wilson intervals and a false-repair rate; "
          f"the verified agent cost {cost('agent')} per 1,000 addresses against {cost('llm_only')} for LLM-only.",
          f"- Wrote the hand-rolled tool-use loop, grounding and completeness checks and a Postgres review queue in Python; total API spend for the whole project was ${usd:.2f}, and the write-up "
          "states where the agent does not beat the rules.", "",
          "## Likely interview questions", "",
          f"**Is the agent better than the rules?** Not on accuracy. On the test split: auto-correct {ac('agent')} against {ac('rules_only')}, and the same false-repair count "
          f"({fr('agent')} against {fr('rules_only')}). What it adds is routing: the {fmt(t['agent']['metrics']['routes']['REVIEW'])} records it sends to review instead of publishing.",
          "",
          f"**Why not just use the LLM?** On the same synthetic test split it auto-corrects more ({ac('llm_only')}) but falsely repairs {fr('llm_only')} of what it accepts, with no verifier, "
          f"against {fr('agent')} for the agent. In a payments setting a wrong accepted address is the expensive error.",
          "",
          f"**Is the cost advantage real?** On the test split, yes ({cost('agent')} against {cost('llm_only')} per 1,000). On the hard set no: {cost('agent', h)} against {cost('llm_only', h)}, "
          "because most hard records reach the model.",
          "",
          "**How reliable are these numbers?** They are on synthetic data that shares a generator and GeoNames with the rules, so they are optimistic. The hard set is small, AI-drafted and "
          "AI-verified. Each system was run once; temperature cannot be set on this model.",
          "",
          f"**Did the verifier catch every bad repair?** No. {t['agent']['metrics']['false_repair']['k']} false repairs got through, the same two failure patterns as the rules-only run; each has real text in the wrong field, which the grounding check cannot see.",
          "",
          f"**What is the weakest country?** India: rules-only auto-correct was {ind['rules_only']} on the test split.",
          "",
          "**Is it CBPR+ compliant?** No. It implements a documented subset of CBPR+ address rules; the validator checks only a small subset, and the real hybrid-address limit is unconfirmed.", ""]
    return "\n".join(L)



def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--hard-set-note", action="store_true", help="write docs/decisions/hard-set-results.md instead")
    ap.add_argument("--readme", action="store_true", help="rewrite the results block of README.md between its marker comments")
    ap.add_argument("--resume-numbers", action="store_true", help="write docs/resume-numbers.md")
    args = ap.parse_args(argv)
    runs = load_runs(args.results_dir)
    if args.readme:
        write_readme(runs, args.results_dir)
        print(f"wrote the results block of {README}")
        return 0
    if args.resume_numbers:
        out = args.out if args.out != OUT else RESUME
        out.write_text(render_resume_numbers(runs, args.results_dir), encoding="utf-8")
        print(f"wrote {out}")
        return 0
    if args.hard_set_note:
        out = args.out if args.out != OUT else HARD_NOTE
        out.write_text(render_hard_note(runs), encoding="utf-8")
        print(f"wrote {out}")
        return 0
    args.out.write_text(render(runs, load_injection_runs(args.results_dir)), encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
