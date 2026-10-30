"""python -m evals.report : generate docs/eval-results.md from the run records in evals/results/ and nothing else.

No number in the output is typed by hand. Percentages carry their n; a bucket with fewer than 5 records shows only counts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

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


def load_runs(results_dir: Path = RESULTS_DIR) -> dict[tuple[str, str, int | None], dict]:
    """Latest run record per (system, split, limit). limit is None for a run over the whole split."""
    latest: dict[tuple[str, str, int | None], dict] = {}
    for path in sorted(results_dir.glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        key = (rec["system"], rec["split"], rec.get("limit"))
        if key not in latest or rec["date"] >= latest[key]["date"]:
            rec["_file"] = path.name
            latest[key] = rec
    return latest


def _pct(x) -> str:
    return "-" if x is None else f"{100 * x:.1f}"


def head_row(system: str, run: dict | None) -> str:
    if run is None:
        return f"| {system} | not run yet | | | | | | | | | |"
    m = run["metrics"]
    r = m["routes"]
    return (f"| {system} | {m['n']} | {fmt(m['exact_all'], True)} | {fmt(m['auto_correct'], True)} | {fmt(m['false_repair'], True)} | "
            f"{fmt(m['hallucinated_records'])} ({m['hallucinated_values']} values) | {fmt(r['ACCEPT'])} | {fmt(r['NEEDS_LLM'])} | {fmt(r['REVIEW'])} | "
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
    lines = ["**Per element** (precision, recall, F1 in percent; n_gold is the number of gold values)", "",
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
        out += [f"**First {lim} records of {split}** (the same records for every system)", "",
                "| system | n | exact_all [95% CI] | auto-correct [95% CI] | **false-repair rate** [95% CI] | hallucinated | ACCEPT | NEEDS_LLM | REVIEW | latency p50 / p95 (ms) | cost per 1,000 (USD) |",
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
    out += ["| system | n | exact_all [95% CI] | auto-correct [95% CI] | **false-repair rate** [95% CI] | hallucinated | ACCEPT | NEEDS_LLM | REVIEW | latency p50 / p95 (ms) | cost per 1,000 (USD) |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in SYSTEM_ORDER:
        out.append(head_row(s, here[s]))
    out.append("")
    for s in SYSTEM_ORDER:
        r = here[s]
        out.append(f"- {s}: " + (f"run {r['date']}, git `{r['git_sha'][:10]}`{' (uncommitted changes)' if r.get('git_dirty') else ''}, "
                                 f"{r['n_records']} records, seed {r['seed']}, file `{r['_file']}`" if r else "not run yet"))
    out.append("")
    base = here["rules_only"]
    if base:
        m = base["metrics"]
        out.append(f"Rules-only field accuracy: {fmt(m['field_accuracy'], True)} of gold values.")
        nt = m["no_town"]
        if nt["n"]:
            out.append(f"Records whose gold has no town: {nt['n']}; the system output a town for {nt['output_a_town']}, "
                       f"accepted one for {nt['accepted_with_a_town']}, and the output town was not in the input for {nt['hallucinated_town']}.")
        out.append("")
        out += element_table(m["per_element"])
        out += subset_tables(split, runs)
        out += bucket_table("By country", m["by_country"])
        out += bucket_table("By tier", m["by_tier"])
        if split == "hard":
            out += bucket_table("By tag (a record counts in every one of its tags)", m["by_tag"])
        fp = list(m["failure_patterns"].items())[:10]
        if fp:
            out += ["**Failure patterns** (count of records; no record ids)", "", "| pattern | records |", "|---|---|"]
            out += [f"| {p} | {c} |" for p, c in fp] + [""]
    return out


def render(runs: dict) -> str:
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--hard-set-note", action="store_true", help="write docs/decisions/hard-set-results.md instead")
    args = ap.parse_args(argv)
    runs = load_runs(args.results_dir)
    if args.hard_set_note:
        out = args.out if args.out != OUT else HARD_NOTE
        out.write_text(render_hard_note(runs), encoding="utf-8")
        print(f"wrote {out}")
        return 0
    args.out.write_text(render(runs), encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
