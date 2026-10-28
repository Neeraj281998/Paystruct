"""The same seed must regenerate byte-identical files."""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

from addrgen.cli import write_jsonl
from addrgen.generate import generate, generate_record
from tests.conftest import GENERATOR_DIR


def _write(path, seed, count=150, **kw):
    write_jsonl(path, generate(seed, count, ["IE", "GB"], **kw))
    return path.read_bytes()


def test_the_project_seed_is_recorded_in_the_seed_file():
    text = (GENERATOR_DIR / "SEED").read_text()
    assert text.strip().isdigit() and text.endswith("\n")


def test_same_seed_gives_identical_bytes(tmp_path, seed):
    assert _write(tmp_path / "a.jsonl", seed) == _write(tmp_path / "b.jsonl", seed)


def test_a_different_seed_gives_different_output(tmp_path, seed):
    assert _write(tmp_path / "a.jsonl", seed) != _write(tmp_path / "b.jsonl", seed + 1)


def test_a_record_does_not_depend_on_how_many_records_are_asked_for(seed):
    short = list(generate(seed, 30, ["IE", "GB"]))
    long = list(generate(seed, 90, ["IE", "GB"]))
    assert long[:30] == short


def test_a_record_depends_only_on_its_own_coordinates(seed):
    assert generate_record(seed, "IE", 7, "hard") == generate_record(seed, "IE", 7, "hard")
    assert generate_record(seed, "IE", 7, "hard") != generate_record(seed, "IE", 8, "hard")


@pytest.mark.parametrize("hash_seed", ["1", "2", "random"])
def test_the_command_line_gives_identical_bytes_whatever_the_hash_seed(tmp_path, seed, hash_seed):
    """A fresh process per run, with Python's string hashing varied, so no set or dict ordering leaks into the output."""
    out = tmp_path / f"cli-{hash_seed}.jsonl"
    env = {**os.environ, "PYTHONHASHSEED": hash_seed}
    subprocess.run([sys.executable, "-m", "addrgen", "--seed", str(seed), "--count", "150", "--countries", "IE,GB", "--out", str(out)],
                   cwd=GENERATOR_DIR, env=env, check=True, capture_output=True)
    assert out.read_bytes() == _write(tmp_path / "inproc.jsonl", seed)


def test_the_command_line_requires_a_seed(tmp_path):
    result = subprocess.run([sys.executable, "-m", "addrgen", "--count", "5", "--out", str(tmp_path / "x.jsonl")],
                            cwd=GENERATOR_DIR, capture_output=True, text=True)
    assert result.returncode != 0 and "--seed" in result.stderr


def test_output_is_utf8_json_lines_with_unix_newlines(tmp_path, seed):
    data = _write(tmp_path / "a.jsonl", seed)
    assert b"\r" not in data and data.endswith(b"\n")
    text = data.decode("utf-8")
    assert "\\u" not in text  # accents are written as characters, not escapes
