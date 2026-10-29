"""The disjointness check, on freshly built splits in a temp directory and on the committed ones."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from addrgen import split_check
from addrgen.split_check import check_splits
from addrgen.splits import dump_jsonl, file_sha256, write_splits

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture()
def splits_dir(tmp_path, seed):
    write_splits(tmp_path, seed)
    return tmp_path


def _records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _rewrite(splits_dir: Path, name: str, records: list[dict], update_manifest: bool = True) -> None:
    path = splits_dir / f"{name}.jsonl"
    path.write_bytes(dump_jsonl(records))
    if update_manifest:
        mpath = splits_dir / "splits.manifest.json"
        manifest = json.loads(mpath.read_text())
        manifest["splits"][name]["sha256"] = file_sha256(path)
        mpath.write_text(json.dumps(manifest))


def test_clean_splits_pass(splits_dir):
    assert check_splits(splits_dir) == []


def test_an_address_in_two_splits_fails(splits_dir):
    dev = _records(splits_dir / "dev.jsonl")
    cal = _records(splits_dir / "calibration.jsonl")
    leaked = dict(dev[0], id="ie-99999")  # same ground truth, different id
    _rewrite(splits_dir, "calibration", cal[:-1] + [leaked])
    assert any("both dev and calibration" in p for p in check_splits(splits_dir))


def test_a_shared_id_fails(splits_dir):
    dev = _records(splits_dir / "dev.jsonl")
    cal = _records(splits_dir / "calibration.jsonl")
    _rewrite(splits_dir, "calibration", [dict(cal[0], id=dev[0]["id"])] + cal[1:])
    assert any(f"id {dev[0]['id']} is in both" in p for p in check_splits(splits_dir))


def test_a_repeat_inside_one_split_fails(splits_dir):
    dev = _records(splits_dir / "dev.jsonl")
    _rewrite(splits_dir, "dev", dev[:-1] + [dict(dev[0], id="ie-88888")])
    assert any("dev repeats an address" in p for p in check_splits(splits_dir))


def test_a_leak_from_the_test_split_is_found_through_the_manifest(splits_dir):
    dev = _records(splits_dir / "dev.jsonl")
    mpath = splits_dir / "splits.manifest.json"
    manifest = json.loads(mpath.read_text())
    from addrgen.splits import key_hash
    manifest["splits"]["test"]["key_hashes"][0] = key_hash(dev[0])
    mpath.write_text(json.dumps(manifest))
    assert any("both dev and test" in p for p in check_splits(splits_dir))


def test_a_changed_test_file_fails(splits_dir):
    with open(splits_dir / "test.jsonl", "ab") as f:
        f.write(b"\n")
    assert any("test.jsonl does not match the manifest hash" in p for p in check_splits(splits_dir))


def test_a_changed_dev_file_fails(splits_dir):
    _rewrite(splits_dir, "dev", _records(splits_dir / "dev.jsonl")[:-1], update_manifest=False)
    assert any("dev.jsonl does not match the manifest hash" in p for p in check_splits(splits_dir))


def test_a_missing_manifest_fails(tmp_path):
    assert check_splits(tmp_path) == [f"{tmp_path / 'splits.manifest.json'} is missing"]


def test_the_test_file_is_not_parsed_by_default(splits_dir, monkeypatch):
    real = split_check._read

    def guarded(path):
        assert Path(path).name != "test.jsonl", "the frozen test split must not be parsed"
        return real(path)

    monkeypatch.setattr(split_check, "_read", guarded)
    assert check_splits(splits_dir) == []
    with pytest.raises(AssertionError, match="must not be parsed"):
        check_splits(splits_dir, parse_test=True)


def test_hard_split_is_included_when_present(splits_dir):
    dev = _records(splits_dir / "dev.jsonl")
    hard = dict(dev[0], id="ie-h001")
    (splits_dir / "hard.jsonl").write_bytes(dump_jsonl([hard]))
    assert any("both dev and hard" in p for p in check_splits(splits_dir))


def test_committed_splits_are_disjoint():
    assert check_splits(REPO / "data" / "splits") == []
