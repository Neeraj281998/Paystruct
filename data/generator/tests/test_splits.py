"""The generated splits: sizes, balance, disjointness, determinism, and the on-disk files."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from addrgen import countries
from addrgen.difficulty import DIFFICULTIES
from addrgen.splits import (GENERATED_SPLITS, SplitSpec, build_all, build_split, counts, dump_jsonl, gold_key,
                            key_hash, write_splits)
from addrgen.validate import check_record

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def built(seed):
    return build_all(seed)


def test_sizes(built):
    assert {n: len(r) for n, r in built.items()} == {"dev": 600, "calibration": 400, "test": 1000}


def test_every_country_has_an_equal_share(built):
    for name, records in built.items():
        by_country = Counter(r["country"] for r in records)
        assert set(by_country) == set(countries.codes())
        assert len(set(by_country.values())) == 1, name


def test_tiers_are_balanced_within_one_record_per_country(built):
    for name, records in built.items():
        for code in countries.codes():
            tiers = Counter(r["difficulty"] for r in records if r["country"] == code)
            assert set(tiers) == set(DIFFICULTIES)
            assert max(tiers.values()) - min(tiers.values()) <= 1, (name, code, tiers)


def test_overall_tiers_are_nearly_equal(built):
    for name, records in built.items():
        tiers = Counter(r["difficulty"] for r in records)
        assert max(tiers.values()) - min(tiers.values()) <= 2, (name, tiers)


def test_no_ground_truth_address_is_in_two_splits_or_twice(built):
    seen: dict[str, str] = {}
    for name, records in built.items():
        for r in records:
            key = gold_key(r)
            assert key not in seen, f"{r['id']} ({name}) repeats an address from {seen.get(key)}"
            seen[key] = name
    assert len(seen) == 2000


def test_ids_are_unique_across_splits(built):
    ids = [r["id"] for records in built.values() for r in records]
    assert len(ids) == len(set(ids))


def test_every_record_is_valid(built):
    for records in built.values():
        for r in records:
            assert check_record(r) == []


def test_build_is_deterministic(seed, built):
    again = build_all(seed)
    assert {n: dump_jsonl(r) for n, r in again.items()} == {n: dump_jsonl(r) for n, r in built.items()}


def test_gold_key_ignores_case_and_spacing():
    a = {"country": "IE", "gold": {"StrtNm": "Main St", "Ctry": "IE"}}
    b = {"country": "IE", "gold": {"Ctry": "IE", "StrtNm": "MAIN  ST "}}
    c = {"country": "GB", "gold": {"StrtNm": "Main St", "Ctry": "GB"}}
    assert gold_key(a) == gold_key(b) != gold_key(c)
    assert key_hash(a) == key_hash(b) != key_hash(c)


def test_a_taken_address_is_skipped_not_reused(seed):
    spec = SplitSpec("probe", 16, 50_000)
    first = build_split(seed, spec, set())
    taken = {gold_key(first[0]), gold_key(first[8])}  # one address from two different countries
    second = build_split(seed, spec, set(taken))
    assert not taken & {gold_key(r) for r in second}
    assert len(second) == 16
    assert {r["id"] for r in first} != {r["id"] for r in second}


def test_size_must_divide_over_the_countries(seed):
    with pytest.raises(ValueError, match="divide evenly"):
        build_split(seed, SplitSpec("odd", 10, 0), set())


def test_split_files_are_lf_utf8_jsonl(built):
    data = dump_jsonl(built["dev"])
    assert b"\r" not in data and data.endswith(b"\n")
    assert [json.loads(line) for line in data.decode("utf-8").splitlines()] == built["dev"]


def test_counts_cover_every_record(built):
    c = counts(built["calibration"])
    assert c["records"] == 400 == sum(c["by_country"].values()) == sum(c["by_country_difficulty"].values())


def test_ranges_do_not_meet():
    firsts = [s.first_index for s in GENERATED_SPLITS]
    assert firsts == sorted(firsts) and all(b - a >= 10_000 for a, b in zip(firsts, firsts[1:]))


def test_write_splits_writes_files_manifest_and_freeze(tmp_path, seed):
    manifest = write_splits(tmp_path, seed)
    assert (tmp_path / "test.sha256").read_text().split()[0] == manifest["splits"]["test"]["sha256"]
    assert manifest["splits"]["dev"]["records"] == 600
    assert len(manifest["splits"]["test"]["key_hashes"]) == 1000
    assert "gold" not in json.dumps(manifest)  # the manifest holds hashes and counts, never addresses


def test_write_splits_never_rewrites_a_frozen_test_split(tmp_path, seed):
    write_splits(tmp_path, seed)
    test = tmp_path / "test.jsonl"
    before = test.read_bytes()
    write_splits(tmp_path, seed)  # same seed: allowed, file left alone
    assert test.read_bytes() == before
    with pytest.raises(SystemExit, match="frozen"):
        write_splits(tmp_path, seed + 1)  # different content: refused
    assert test.read_bytes() == before


def test_refreeze_replaces_the_test_split_and_its_hash_only_when_asked(tmp_path, seed):
    write_splits(tmp_path, seed)
    old_hash = (tmp_path / "test.sha256").read_text()
    with pytest.raises(SystemExit):
        write_splits(tmp_path, seed + 1)
    assert (tmp_path / "test.sha256").read_text() == old_hash
    manifest = write_splits(tmp_path, seed + 1, refreeze=True)
    assert (tmp_path / "test.sha256").read_text().split()[0] == manifest["splits"]["test"]["sha256"] != old_hash.split()[0]


def test_committed_dev_and_calibration_match_the_seed(built):
    for name in ("dev", "calibration"):
        assert (REPO / "data" / "splits" / f"{name}.jsonl").read_bytes() == dump_jsonl(built[name])
