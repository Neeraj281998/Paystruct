"""scripts/verify_frozen.py: fails when the frozen test split changes."""
from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "verify_frozen.py"
_spec = importlib.util.spec_from_file_location("verify_frozen", SCRIPT)
verify_frozen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verify_frozen)


@pytest.fixture()
def frozen(tmp_path):
    data = b'{"id": "x"}\n'
    (tmp_path / "test.jsonl").write_bytes(data)
    (tmp_path / "test.sha256").write_text(f"{hashlib.sha256(data).hexdigest()}  test.jsonl\n")
    return tmp_path


def test_intact_file_passes(frozen):
    assert verify_frozen.verify(frozen) is None


def test_any_change_fails(frozen):
    (frozen / "test.jsonl").write_bytes(b'{"id": "y"}\n')
    assert "has changed" in verify_frozen.verify(frozen)


def test_a_trailing_newline_is_a_change(frozen):
    with open(frozen / "test.jsonl", "ab") as f:
        f.write(b"\n")
    assert "has changed" in verify_frozen.verify(frozen)


def test_missing_hash_or_file_fails(frozen):
    (frozen / "test.sha256").unlink()
    assert "not frozen" in verify_frozen.verify(frozen)
    (frozen / "test.sha256").write_text("")
    assert "empty" in verify_frozen.verify(frozen)
    (frozen / "test.sha256").write_text("ab  test.jsonl\n")
    (frozen / "test.jsonl").unlink()
    assert "missing" in verify_frozen.verify(frozen)


def test_it_never_prints_the_contents(frozen, capsys, monkeypatch):
    (frozen / "test.jsonl").write_bytes(b'{"secret": "SENTINEL-ADDRESS"}\n')
    monkeypatch.setattr(verify_frozen, "SPLITS", frozen)
    assert verify_frozen.main() == 1
    captured = capsys.readouterr()
    assert "SENTINEL-ADDRESS" not in captured.out + captured.err


def test_committed_test_split_is_still_frozen():
    result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
