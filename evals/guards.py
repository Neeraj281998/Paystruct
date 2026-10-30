"""Which splits may be run, and how. The frozen test split is run once, on Day 5, with --final."""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FREE = ("dev", "calibration")
EXPLICIT = ("hard",)          # runs only when asked for with --split hard
TEST = "test"

# Flipped by the owner for the one final run (docs/decisions/final-run-protocol.md). The test split still needs --final, and
# scripts/verify_frozen.py must pass first.
TEST_RUN_ENABLED = True

WARNING = (
    "\n" + "!" * 78 + "\n"
    "THE FROZEN TEST SPLIT. It is run ONCE, for the final numbers, and never used for tuning.\n"
    "Nothing may be changed in the rules, prompts or thresholds after this run.\n" + "!" * 78 + "\n"
)


class Refused(Exception):
    pass


@dataclass
class Decision:
    split: str
    path: Path
    warning: str = ""


def _verify_frozen() -> str | None:
    spec = importlib.util.spec_from_file_location("verify_frozen", REPO_ROOT / "scripts" / "verify_frozen.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.verify()


def check_split(split: str, final: bool = False, test_enabled: bool | None = None, verify=None) -> Decision:
    """Return the decision to run `split`, or raise Refused. Reads no split file itself."""
    enabled = TEST_RUN_ENABLED if test_enabled is None else test_enabled
    path = REPO_ROOT / "data" / "splits" / f"{split}.jsonl"
    if split in FREE or split in EXPLICIT:
        return Decision(split, path)
    if split == TEST:
        if not final:
            raise Refused("The test split needs the explicit --final flag, and it is run once, on Day 5. Refused.")
        if not enabled:
            raise Refused(WARNING + "REFUSED: the test split is not enabled in this session (evals/guards.py: TEST_RUN_ENABLED is False).\n")
        problem = (verify or _verify_frozen)()
        if problem:
            raise Refused(WARNING + f"REFUSED: scripts/verify_frozen.py says the test split is not intact: {problem}\n")
        return Decision(split, path, WARNING)
    raise Refused(f"Unknown split '{split}'. Allowed: {', '.join(FREE + EXPLICIT)}; test only with --final on Day 5.")


def load_records(decision: Decision) -> list[dict]:
    import json
    return [json.loads(l) for l in decision.path.read_text(encoding="utf-8").splitlines() if l.strip()]
