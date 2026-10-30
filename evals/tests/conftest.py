"""Safety net for every evals test: no test may hash or read the real frozen test split.

The guard calls scripts/verify_frozen.py, which hashes data/splits/test.jsonl. In tests that call is replaced, so a guard that is
enabled can never reach the real file; a test that wants the check to pass passes its own `verify` to check_split.
"""
import pytest

from evals import guards


@pytest.fixture(autouse=True)
def never_touch_the_real_test_split(monkeypatch):
    monkeypatch.setattr(guards, "_verify_frozen", lambda: "tests never hash the real frozen test split")
