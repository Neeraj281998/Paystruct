"""python -m evals.calibrate [run_record.json] [--apply]

Chooses the repair threshold from the stored per-record details of an AGENT run on the CALIBRATION split (never dev, hard or test).
For thresholds 0.50 to 0.99 it prints the ACCEPT coverage and the accepted-wrong count and rate with its Wilson 95% interval, writes the
table as a CSV and a plain SVG of coverage against false-repair rate, and names the point that maximises coverage subject to an observed
false-repair rate of at most 1% among the accepted. It changes nothing unless --apply is given.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path

from agent.rules.scoring import score_record
from agent.rules.xsd import REPO_ROOT
from evals.stats import wilson

RESULTS_DIR = REPO_ROOT / "evals" / "results"
ROUTING_YML = REPO_ROOT / "agent" / "config" / "routing.yml"
THRESHOLD_DOC = REPO_ROOT / "docs" / "decisions" / "threshold.md"
THRESHOLDS = [round(0.50 + 0.01 * i, 2) for i in range(50)]      # 0.50 .. 0.99
MAX_FALSE_REPAIR = 0.01       # observed rate among the accepted
WIDE_UPPER = 0.05             # a Wilson upper bound above this is said plainly
LOW_COVERAGE_SHARE = 0.5      # a point that keeps less than this share of the coverage at 0.50 reaches its rate by discarding most of it


class CalibrationError(Exception):
    pass


def candidates(run: dict) -> list[tuple[float, bool]]:
    """(confidence, is correct) for every record the pipeline would publish at some threshold: repaired, or rejected only for low confidence."""
    if run.get("system") != "agent":
        raise CalibrationError("the threshold is calibrated on an agent run")
    if run.get("split") != "calibration":
        raise CalibrationError(f"the threshold is set on the calibration split only, not on '{run.get('split')}'")
    if "records" not in run:
        raise CalibrationError("this run record has no per-record details")
    out = []
    for r in run["records"]:
        x = r["system_extra"]
        conf = x.get("confidence")
        if conf is None:
            continue
        if x.get("status") == "repaired":
            fields = dict(r["output"])
        elif "LOW_CONFIDENCE" in (x.get("reasons") or []):
            proposals = [a["proposal"] for a in (x.get("attempt_log") or []) if a.get("proposal")]
            fields = dict(proposals[-1]) if proposals else dict((x.get("rules") or {}).get("fields") or {})
        else:
            continue
        fields.pop("AdrLine", None)
        out.append((float(conf), score_record(fields, r["gold"], r["country"]).exact))
    return out


def table(run: dict) -> list[dict]:
    cands = candidates(run)
    n = run["n_records"]
    rows = []
    for t in THRESHOLDS:
        acc = [ok for c, ok in cands if c >= t]
        wrong = sum(not ok for ok in acc)
        ci = wilson(wrong, len(acc))
        rows.append({"threshold": t, "accepted": len(acc), "accepted_wrong": wrong, "coverage": len(acc) / n if n else 0.0,
                     "false_repair_rate": wrong / len(acc) if acc else 0.0, "wilson_low": ci[0] if ci else None, "wilson_high": ci[1] if ci else None})
    return rows


def choose(rows: list[dict]) -> dict | None:
    """Maximise coverage subject to an observed false-repair rate of at most 1%; ties go to the higher threshold."""
    ok = [r for r in rows if r["accepted"] > 0 and r["false_repair_rate"] <= MAX_FALSE_REPAIR]
    return max(ok, key=lambda r: (r["coverage"], r["threshold"])) if ok else None


def assess(rows: list[dict], best: dict | None) -> list[str]:
    """Plain statements about the chosen point."""
    if best is None:
        return ["No threshold from 0.50 to 0.99 reaches an observed false-repair rate of 1% or less among the accepted. Nothing is chosen."]
    notes = []
    if best["wilson_high"] is not None and best["wilson_high"] > WIDE_UPPER:
        notes.append(f"At the chosen point the Wilson 95% upper bound of the false-repair rate is {100 * best['wilson_high']:.1f}%, above 5%: with only "
                     f"{best['accepted']} accepted records the data cannot show that the false-repair rate is below 5%.")
    base = rows[0]["coverage"]
    if base > 0 and best["coverage"] < LOW_COVERAGE_SHARE * base:
        notes.append(f"The chosen point keeps {100 * best['coverage']:.1f}% coverage against {100 * base:.1f}% at threshold 0.50: it meets the 1% limit "
                     "by discarding most of the coverage. Do not apply it without reading the table.")
    if best["accepted_wrong"] == 0:
        notes.append("The chosen point has zero accepted-wrong records, which is an observed zero, not a guarantee (see the Wilson upper bound).")
    return notes


def write_csv(rows: list[dict], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["threshold", "accepted", "accepted_wrong", "coverage", "false_repair_rate", "wilson_low", "wilson_high"])
        for r in rows:
            w.writerow([r["threshold"], r["accepted"], r["accepted_wrong"], f"{r['coverage']:.4f}", f"{r['false_repair_rate']:.4f}",
                        "" if r["wilson_low"] is None else f"{r['wilson_low']:.4f}", "" if r["wilson_high"] is None else f"{r['wilson_high']:.4f}"])


def write_svg(rows: list[dict], best: dict | None, path: Path) -> None:
    """Plain SVG, standard library only: coverage (y) against false-repair rate (x), one point per threshold."""
    W, H, L, R, T, B = 640, 420, 60, 20, 30, 50
    xmax = max([r["false_repair_rate"] for r in rows if r["accepted"]] + [0.02]) * 1.1
    px = lambda x: L + (W - L - R) * x / xmax
    py = lambda y: H - B - (H - T - B) * y
    pts = [(px(r["false_repair_rate"]), py(r["coverage"]), r) for r in rows if r["accepted"]]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in pts)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="sans-serif" font-size="11">',
             f'<rect width="{W}" height="{H}" fill="white"/>',
             f'<line x1="{L}" y1="{H - B}" x2="{W - R}" y2="{H - B}" stroke="#444"/><line x1="{L}" y1="{T}" x2="{L}" y2="{H - B}" stroke="#444"/>',
             f'<text x="{W / 2:.0f}" y="{H - 10}" text-anchor="middle">false-repair rate among accepted (%)</text>',
             f'<text x="14" y="{H / 2:.0f}" text-anchor="middle" transform="rotate(-90 14 {H / 2:.0f})">ACCEPT coverage (%)</text>',
             f'<text x="{W / 2:.0f}" y="18" text-anchor="middle">Coverage against false-repair rate, thresholds 0.50 to 0.99 (calibration split)</text>']
    for i in range(0, 6):
        yv = i / 5
        parts.append(f'<line x1="{L - 4}" y1="{py(yv):.1f}" x2="{L}" y2="{py(yv):.1f}" stroke="#444"/><text x="{L - 8}" y="{py(yv) + 4:.1f}" text-anchor="end">{int(yv * 100)}</text>')
    for i in range(0, 6):
        xv = xmax * i / 5
        parts.append(f'<line x1="{px(xv):.1f}" y1="{H - B}" x2="{px(xv):.1f}" y2="{H - B + 4}" stroke="#444"/><text x="{px(xv):.1f}" y="{H - B + 16}" text-anchor="middle">{100 * xv:.1f}</text>')
    if pts:
        parts.append(f'<polyline points="{line}" fill="none" stroke="#1f6feb" stroke-width="1.5"/>')
    for x, y, r in pts:
        mark = abs(r["threshold"] - round(r["threshold"], 1)) < 1e-9
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{3 if mark else 1.8}" fill="#1f6feb"/>')
        if mark:
            parts.append(f'<text x="{x + 5:.1f}" y="{y - 5:.1f}">{r["threshold"]:.1f}</text>')
    if best:
        parts.append(f'<circle cx="{px(best["false_repair_rate"]):.1f}" cy="{py(best["coverage"]):.1f}" r="6" fill="none" stroke="#d1242f" stroke-width="2"/>'
                     f'<text x="{px(best["false_repair_rate"]) + 9:.1f}" y="{py(best["coverage"]) + 14:.1f}" fill="#d1242f">chosen {best["threshold"]:.2f}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def apply_threshold(best: dict, run_file: str, n_records: int, routing_path: Path | None = None, doc_path: Path | None = None,
                    today: str | None = None) -> None:
    """Write the threshold into routing.yml and append the reason, the date and the run record id to docs/decisions/threshold.md."""
    routing_path = routing_path or ROUTING_YML          # looked up at call time, so a test can point them elsewhere
    doc_path = doc_path or THRESHOLD_DOC
    today = today or dt.date.today().isoformat()
    text = routing_path.read_text(encoding="utf-8")
    new = re.sub(r"^threshold:.*$", f"threshold: {best['threshold']:.2f}   # set on the calibration split by evals/calibrate.py --apply ({today}, {run_file}); see docs/decisions/threshold.md",
                 text, count=1, flags=re.M)
    if new == text:
        raise CalibrationError("could not find the threshold line in routing.yml")
    routing_path.write_text(new, encoding="utf-8")
    if not doc_path.exists():
        doc_path.write_text("# Repair threshold\n\nThe REPAIRED threshold in `agent/config/routing.yml` is chosen on the calibration split by `python -m evals.calibrate`: "
                            "the point with the most ACCEPT coverage whose observed false-repair rate among the accepted is at most 1%.\n\n"
                            "**Caveat.** The calibration split was already used for reporting (the Day 2 audit and the Day 3 baseline) and its failure patterns "
                            "informed earlier fixes, so the threshold chosen on it is slightly optimistic. The interval below is the honest statement of how little a "
                            "few hundred records can show.\n", encoding="utf-8")
    ci = "" if best["wilson_high"] is None else f"; Wilson 95% interval {100 * best['wilson_low']:.1f}% to {100 * best['wilson_high']:.1f}%"
    with open(doc_path, "a", encoding="utf-8") as f:
        f.write(f"\n## {today}: threshold {best['threshold']:.2f}\n\n- Reason: the point with the most ACCEPT coverage ({100 * best['coverage']:.1f}% of {n_records} calibration records) "
                f"whose observed false-repair rate among the accepted is at most 1% ({best['accepted_wrong']} wrong of {best['accepted']} accepted = "
                f"{100 * best['false_repair_rate']:.2f}%{ci}).\n- Run record: `{run_file}`.\n- Applied with `python -m evals.calibrate --apply`; not applied automatically.\n")


def latest_calibration_run(results_dir: Path = RESULTS_DIR) -> Path | None:
    best = None
    for path in sorted(Path(results_dir).glob("*.json")):
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if run.get("system") == "agent" and run.get("split") == "calibration" and "records" in run and not run.get("subset"):
            if best is None or run["date"] >= best[0]:
                best = (run["date"], path)
    return best[1] if best else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run_record", nargs="?", type=Path, help="an agent run record on the calibration split (default: the latest full one)")
    ap.add_argument("--apply", action="store_true", help="write the chosen threshold to agent/config/routing.yml and docs/decisions/threshold.md")
    ap.add_argument("--accept-low-coverage", action="store_true", help="allow --apply when the chosen point discards most of the coverage")
    ap.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = ap.parse_args(argv)
    path = args.run_record or latest_calibration_run(args.results_dir)
    if path is None:
        sys.stderr.write("no agent run record on the calibration split with per-record details found\n")
        return 2
    run = json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        rows = table(run)
    except CalibrationError as e:
        sys.stderr.write(f"REFUSED: {e}\n")
        return 2
    best = choose(rows)
    print(f"run record {Path(path).name}: {run['n_records']} calibration records, threshold now {_current_threshold()}")
    print("threshold  accepted  wrong  coverage   wrong/accepted   Wilson 95%")
    for r in rows:
        ci = "      n/a" if r["wilson_low"] is None else f"{100 * r['wilson_low']:5.1f}-{100 * r['wilson_high']:5.1f}%"
        mark = "  <== chosen" if best and r["threshold"] == best["threshold"] else ""
        print(f"   {r['threshold']:.2f}    {r['accepted']:6d}  {r['accepted_wrong']:5d}   {100 * r['coverage']:6.1f}%   {100 * r['false_repair_rate']:7.2f}%     {ci}{mark}")
    notes = assess(rows, best)
    print()
    for n in notes:
        print("NOTE:", n)
    stem = Path(path).stem
    write_csv(rows, args.results_dir / f"threshold_{stem}.csv")
    write_svg(rows, best, args.results_dir / f"threshold_{stem}.svg")
    print(f"wrote threshold_{stem}.csv and threshold_{stem}.svg in {args.results_dir}")
    if not args.apply:
        print("Nothing was changed. Review the table, then run again with --apply to write the threshold.")
        return 0
    if best is None:
        sys.stderr.write("REFUSED: no point to apply\n")
        return 2
    if run.get("aborted_by_budget"):
        sys.stderr.write("REFUSED: the run was stopped by its budget, so it does not cover the whole calibration split\n")
        return 2
    low = any("discarding most of the coverage" in n for n in notes)
    if low and not args.accept_low_coverage:
        sys.stderr.write("REFUSED: the chosen point discards most of the coverage; read the table and pass --accept-low-coverage to apply it anyway\n")
        return 2
    apply_threshold(best, Path(path).name, run["n_records"])
    print(f"applied: threshold {best['threshold']:.2f} written to agent/config/routing.yml and docs/decisions/threshold.md")
    return 0


def _current_threshold() -> str:
    m = re.search(r"^threshold:\s*([0-9.]+)", ROUTING_YML.read_text(encoding="utf-8"), flags=re.M)
    return m.group(1) if m else "?"


if __name__ == "__main__":
    raise SystemExit(main())
