"""routing.yml is loadable and its threshold is sane. The only tests that read the file's threshold are about the file itself
(this one) and about the applied threshold on purpose (test_with_the_applied_threshold_...)."""
from pathlib import Path

import yaml

from agent.repair.config import CONFIG_DIR, load_routing

ROUTING = CONFIG_DIR / "routing.yml"


def test_routing_yml_parses_and_has_every_key_the_pipeline_reads():
    cfg = yaml.safe_load(ROUTING.read_text(encoding="utf-8"))
    for key in ("threshold", "max_attempts", "max_tool_calls", "max_cost_usd_per_payment", "request_timeout_s", "api_retries", "api_backoff_s",
                "max_payment_tries", "lease_seconds", "max_tokens", "effort", "confidence"):
        assert key in cfg, key
    for key in ("base", "agree_rules_weight", "gazetteer_agree", "gazetteer_unchecked", "attempt_penalty", "model_confidence_weight", "unsupported_cap"):
        assert key in cfg["confidence"], key
    assert load_routing()["threshold"] == cfg["threshold"]


def test_the_threshold_is_within_the_range_the_calibration_searches():
    t = yaml.safe_load(ROUTING.read_text(encoding="utf-8"))["threshold"]
    assert isinstance(t, float) and 0.50 <= t <= 0.99


def test_the_threshold_stays_above_the_unsupported_cap():
    cfg = yaml.safe_load(ROUTING.read_text(encoding="utf-8"))
    assert cfg["confidence"]["unsupported_cap"] < cfg["threshold"]       # a field with no support can never reach REPAIRED


def test_the_header_says_the_confidence_constants_are_frozen():
    head = ROUTING.read_text(encoding="utf-8").splitlines()[:6]
    text = "\n".join(head)
    assert "calibration" in text and "FROZEN" in text and "invalidates the threshold" in text


def test_no_other_test_reads_the_threshold_from_the_file():
    """A recalibration must not change what a test tests: only this file and the applied-threshold test may read it."""
    here = Path(__file__).resolve().parent
    offenders = []
    for path in list(here.glob("test_*.py")) + list((here.parents[1] / "evals" / "tests").glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        if path.name == "test_routing_config.py":
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if 'load_routing()["threshold"]' in line or "routing['threshold']" in line and "load_routing" in line:
                offenders.append(f"{path.name}:{i}")
    assert offenders == []
