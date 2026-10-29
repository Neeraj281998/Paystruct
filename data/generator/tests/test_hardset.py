"""The hard-set authoring format: validator, converter and scripts. Uses the committed example entries and mutations."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from addrgen import countries
from addrgen.hardset import TARGET_SIZE, build_records, to_record, validate_dir, validate_entry
from addrgen.limits import GOLD_FIELDS

REPO = Path(__file__).resolve().parents[3]
HARD_DIR = REPO / "data" / "hard_set"

GOOD = {
    "id": "ie-h001", "tags": ["county", "no_country"], "raw_lines": ["Forge House", "Kinvara, Co. Galway H91 W3R7"],
    "gold": {"BldgNm": "Forge House", "PstCd": "H91 W3R7", "TwnNm": "Kinvara", "CtrySubDvsn": "Co. Galway", "Ctry": "IE"},
    "country_hint": "IE",
}


def problems(**changes) -> list[str]:
    entry = copy.deepcopy(GOOD)
    for k, v in changes.items():
        if v is None:
            entry.pop(k, None)
        else:
            entry[k] = v
    return validate_entry(entry, "IE")


def test_a_good_entry_is_valid():
    assert problems() == []


@pytest.mark.parametrize("changes, expected", [
    ({"id": "gb-h001"}, "does not match the file country"),
    ({"id": "ie-1"}, "must look like"),
    ({"id": "ie-x01"}, "only examples may use them"),
    ({"raw_lines": None}, "raw_lines must be"),
    ({"raw_lines": []}, "raw_lines must be"),
    ({"raw_lines": ["x"] * 8, "gold": {"TwnNm": "x", "Ctry": "IE"}}, "8 raw lines"),
    ({"raw_lines": ["Forge House", "Kinvara, Co. Galway H91 W3R7 " + "x" * 70]}, "over 70 characters"),
    ({"raw_lines": ["Forge House", " "]}, "blank raw line"),
    ({"tags": ["county", "nonsense"]}, "unknown tags"),
    ({"tags": ["county", "county", "no_country"]}, "duplicate tags"),
    ({"gold": {"BldgNm": "Forge House", "Ctry": "IE"}}, "missing the required TwnNm"),
    ({"gold": {"TwnNm": "Kinvara"}}, "missing the required Ctry"),
    ({"gold": {"TwnNm": "Kinvara", "Ctry": "GB"}}, "file is for IE"),
    ({"gold": {"TwnNm": "Limerick", "Ctry": "IE"}}, "does not appear in the raw lines"),
    ({"gold": {"TwnNm": "Kinvara", "Ctry": "IE", "Dept": "Sales"}}, "not used in v1"),
    ({"gold": {"TwnNm": "Kinvara", "Ctry": "IE", "PstBx": "PO Box 12345678901"}}, "does not appear"),
    ({"gold": {"TwnNm": "Kinvara", "Ctry": "IE", "StrtNm": "", }}, "non-empty string"),
    ({"gold": {"TwnNm": " Kinvara", "Ctry": "IE"}}, "outer whitespace"),
    ({"gold": {"TwnNm": "Kinvara", "Ctry": "Ireland"}}, "XSD pattern"),
    ({"country_hint": None}, "no_country needs country_hint"),
    ({"tags": ["county"]}, "country_hint is only for no_country"),
    ({"tags": ["no_country", "country_name"]}, "cannot both be set"),
    ({"surprise": 1}, "unknown keys"),
])
def test_each_rule_is_enforced(changes, expected):
    assert any(expected in p for p in problems(**changes)), problems(**changes)


def test_gold_may_not_exceed_xsd_lengths():
    long_pc = "H91" + "9" * 20
    result = problems(raw_lines=["Forge House", f"Kinvara {long_pc}"],
                      gold={"TwnNm": "Kinvara", "PstCd": long_pc, "Ctry": "IE"}, tags=[], country_hint=None)
    assert any("XSD maximum 16" in p for p in result)


def test_a_po_box_has_no_street():
    result = problems(raw_lines=["PO Box 12 Main St", "Cork"], gold={"PstBx": "PO Box 12", "StrtNm": "Main St", "TwnNm": "Cork", "Ctry": "IE"},
                      tags=["po_box", "no_country"])
    assert any("PO box address has no StrtNm" in p for p in result)


def test_grounding_ignores_case_and_spacing():
    assert problems(raw_lines=["FORGE   HOUSE", "KINVARA, CO. GALWAY H91 W3R7"]) == []


def test_example_notes_must_say_example():
    entry = dict(copy.deepcopy(GOOD), id="ie-x01", example=True, note="demo")
    assert any("note must start with EXAMPLE" in p for p in validate_entry(entry, "IE"))
    entry["note"] = "EXAMPLE: format only"
    assert validate_entry(entry, "IE") == []


def test_committed_files_are_valid_with_two_marked_examples_each():
    found, entries = validate_dir(HARD_DIR)
    assert found == []
    for code in countries.codes():
        examples = [e for c, e in entries if c == code and e.get("example")]
        assert len(examples) == 2 and all(e["note"].startswith("EXAMPLE") for e in examples), code


def test_the_hand_written_entries_do_not_exceed_the_target():
    _, entries = validate_dir(HARD_DIR)
    assert len([e for _, e in entries if not e.get("example")]) <= TARGET_SIZE


def examples_only(tmp_path):
    """A copy of the hard-set files with the hand-written entries removed, so only the two examples per country remain."""
    for f in HARD_DIR.glob("*.yaml"):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        data["entries"] = [e for e in data["entries"] if e.get("example")]
        (tmp_path / f.name).write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return tmp_path


def test_every_country_has_a_file_and_a_missing_one_is_reported(tmp_path):
    for f in HARD_DIR.glob("*.yaml"):
        if f.stem != "NL":
            (tmp_path / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    found, _ = validate_dir(tmp_path)
    assert found == ["NL.yaml is missing"]


def test_file_country_must_match_its_name(tmp_path):
    for f in HARD_DIR.glob("*.yaml"):
        (tmp_path / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    text = (tmp_path / "DE.yaml").read_text(encoding="utf-8").replace("country: DE", "country: FR", 1)
    (tmp_path / "DE.yaml").write_text(text, encoding="utf-8")
    assert any("`country` must be DE" in p for p in validate_dir(tmp_path)[0])


def test_duplicate_ids_are_reported(tmp_path):
    for f in HARD_DIR.glob("*.yaml"):
        (tmp_path / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    data = yaml.safe_load((tmp_path / "IE.yaml").read_text(encoding="utf-8"))
    data["entries"].append(copy.deepcopy(data["entries"][0]))
    (tmp_path / "IE.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    assert any("duplicate id" in p for p in validate_dir(tmp_path)[0])


def test_converter_leaves_examples_out_by_default(tmp_path):
    only = examples_only(tmp_path)
    assert build_records(only, allow_partial=True) == []
    assert len(build_records(only, include_examples=True, allow_partial=True)) == 16
    assert not any("-x" in r["id"] for r in build_records(HARD_DIR, allow_partial=True))


def test_converter_demands_exactly_100(tmp_path):
    only = examples_only(tmp_path)
    with pytest.raises(ValueError, match=f"has {TARGET_SIZE}"):
        build_records(only)
    with pytest.raises(ValueError, match=f"has {TARGET_SIZE}"):
        build_records(only, include_examples=True)


def test_converter_stops_on_an_invalid_entry(tmp_path):
    for f in HARD_DIR.glob("*.yaml"):
        (tmp_path / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "IE.yaml").write_text((tmp_path / "IE.yaml").read_text(encoding="utf-8").replace("Forge House\"", "Forge Hous\"", 1))
    with pytest.raises(ValueError, match="does not appear in the raw lines"):
        build_records(tmp_path, include_examples=True, allow_partial=True)


def test_record_format_matches_the_generator():
    entry = copy.deepcopy(GOOD)
    entry["gold"] = dict(reversed(list(entry["gold"].items())))  # authoring order does not matter
    rec = to_record(entry)
    assert list(rec) == ["id", "country", "difficulty", "tags", "raw_lines", "gold", "country_hint"]
    assert list(rec["gold"]) == [f for f in GOLD_FIELDS if f in rec["gold"]]
    assert rec["difficulty"] == "hard" and rec["country"] == "IE" and rec["tags"] == ["county", "no_country"]


def test_difficulty_is_computed_not_written():
    easy = dict(copy.deepcopy(GOOD), tags=[], country_hint=None)
    assert to_record(easy)["difficulty"] == "easy"
    assert to_record(dict(easy, tags=["flat"]))["difficulty"] == "medium"
    assert to_record(dict(easy, tags=["landmark"]))["difficulty"] == "hard"


def test_example_records_load_as_json_lines(tmp_path):
    (tmp_path / "ex").mkdir()
    records = build_records(examples_only(tmp_path / "ex"), include_examples=True, allow_partial=True)
    assert all(r["id"].split("-")[1].startswith("x") for r in records)
    assert {r["country"] for r in records} == set(countries.codes())
    from addrgen.hardset import write_jsonl
    write_jsonl(tmp_path / "h.jsonl", records)
    assert [json.loads(l) for l in (tmp_path / "h.jsonl").read_text(encoding="utf-8").splitlines()] == records


def _run(script, *args):
    return subprocess.run([sys.executable, str(REPO / "scripts" / script), *args], capture_output=True, text=True)


def test_validate_script_passes_on_the_committed_files():
    result = _run("validate_hard_set.py")
    assert result.returncode == 0 and "of 100 hand-written entries, 16 examples" in result.stdout


def test_build_script_refuses_a_partial_set_and_writes_with_the_flag(tmp_path):
    (tmp_path / "ex").mkdir()
    only = examples_only(tmp_path / "ex")
    out = tmp_path / "hard.jsonl"
    assert _run("build_hard_set.py", "--dir", str(only), "--out", str(out)).returncode == 1 and not out.exists()
    assert _run("build_hard_set.py", "--dir", str(only), "--out", str(out), "--allow-partial", "--include-examples").returncode == 0
    assert len(out.read_text(encoding="utf-8").splitlines()) == 16


def test_committed_hard_jsonl_is_empty_or_matches_the_yaml():
    """The owner builds hard.jsonl after reviewing the drafts; until then it stays empty."""
    path = REPO / "data" / "splits" / "hard.jsonl"
    records = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    assert records == [] or records == build_records(HARD_DIR, allow_partial=True)


def test_partial_postcode_and_not_in_geonames_are_accepted():
    entry = dict(copy.deepcopy(GOOD), tags=["county", "no_country", "partial_postcode", "not_in_geonames"])
    assert validate_entry(entry, "IE") == []
    assert validate_entry(dict(copy.deepcopy(GOOD), tags=["county", "no_country", "not_in_geonames"]), "IE") == []


def test_the_two_tags_do_not_change_the_difficulty_tier():
    from addrgen.difficulty import difficulty_of
    base = {"flat"}
    assert difficulty_of(base | {"partial_postcode", "not_in_geonames"}) == difficulty_of(base) == "medium"
    assert difficulty_of({"not_in_geonames"}) == "easy"


def test_the_generator_never_writes_the_hand_written_only_tags(records):
    used = {t for r in records for t in r["tags"]}
    assert not used & {"partial_postcode", "not_in_geonames", "no_town"}


def test_no_town_entry_has_no_twnnm_and_is_valid():
    entry = {"id": "ie-h001", "tags": ["no_country", "no_town", "partial_postcode"], "country_hint": "IE",
             "raw_lines": ["Unit 5 Fenway Business Park", "D24"],
             "gold": {"Room": "Unit 5", "BldgNm": "Fenway Business Park", "PstCd": "D24", "Ctry": "IE"}}
    assert validate_entry(entry, "IE") == []


def test_no_town_forbids_twnnm_and_still_requires_ctry():
    base = {"id": "ie-h001", "tags": ["no_country", "no_town"], "country_hint": "IE",
            "raw_lines": ["12 Main St", "Cork"], "gold": {"StrtNm": "Main St", "Ctry": "IE"}}
    assert validate_entry(base, "IE") == []
    with_town = dict(base, gold={"StrtNm": "Main St", "TwnNm": "Cork", "Ctry": "IE"})
    assert any("no_town record has no TwnNm" in p for p in validate_entry(with_town, "IE"))
    no_ctry = dict(base, gold={"StrtNm": "Main St"})
    assert any("missing the required Ctry" in p for p in validate_entry(no_ctry, "IE"))


def test_a_missing_town_without_the_tag_is_still_an_error():
    entry = {"id": "ie-h001", "tags": ["no_country"], "country_hint": "IE", "raw_lines": ["12 Main St"],
             "gold": {"StrtNm": "Main St", "Ctry": "IE"}}
    assert any("missing the required TwnNm" in p for p in validate_entry(entry, "IE"))


def test_no_town_makes_a_record_hard():
    from addrgen.difficulty import difficulty_of
    assert difficulty_of({"no_town"}) == "hard" and difficulty_of({"flat", "no_town"}) == "hard"
    assert difficulty_of({"partial_postcode", "not_in_geonames"}) == "easy"  # the other two hand-written tags do not


def test_a_no_town_entry_converts_to_a_hard_record():
    entry = {"id": "fr-h001", "tags": ["country_name", "no_town"], "raw_lines": ["27 rue des Acacias", "69003", "France"],
             "gold": {"BldgNb": "27", "StrtNm": "rue des Acacias", "PstCd": "69003", "Ctry": "FR"}}
    assert validate_entry(entry, "FR") == []
    assert to_record(entry)["difficulty"] == "hard"


def test_every_committed_no_town_entry_converts_to_a_hard_record():
    _, entries = validate_dir(HARD_DIR)
    tagged = [e for _, e in entries if "no_town" in e.get("tags", [])]
    assert len(tagged) >= 8 and all(to_record(e)["difficulty"] == "hard" for e in tagged)
