"""The message builder: skeletons validate against the XSDs, faults behave, and the sample set reproduces."""
from __future__ import annotations

import json
import random
from pathlib import Path

import pytest
from lxml import etree

from addrgen import countries
from addrgen.limits import MAX_LINE_LENGTH, MAX_LINES
from addrgen.messages import (FAULTS, PACS008, PAIN001, apply_fault, build_message, build_messages, fault_missing_country,
                              fault_too_many_lines, fault_town_in_line, read_jobs, validate_xml, write_messages)
from addrgen.splits import dump_jsonl, gold_key
from addrgen.stats import read_jsonl

REPO = Path(__file__).resolve().parents[3]


def rec(country, lines, gold, tags=()):
    return {"id": f"{country.lower()}-00001", "country": country, "difficulty": "easy", "tags": sorted(tags),
            "raw_lines": lines, "gold": gold}


IE = rec("IE", ["14 Main St", "Dublin 1 D01 K2X7", "Ireland"],
         {"StrtNm": "Main St", "BldgNb": "14", "PstCd": "D01 K2X7", "TwnNm": "Dublin 1", "Ctry": "IE"}, ["country_name"])
FR = rec("FR", ["12 Rue des Tilleuls", "69003 Lyon", "France"],
         {"StrtNm": "Rue des Tilleuls", "BldgNb": "12", "PstCd": "69003", "TwnNm": "Lyon", "Ctry": "FR"}, ["country_name"])


def jobs(a="IE", b="FR", lines_a=("14 Main St", "Dublin 1"), lines_b=("12 Rue des Tilleuls", "69003 Lyon")):
    return [{"country": a, "lines": list(lines_a)}, {"country": b, "lines": list(lines_b)}]


# ---- skeletons --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("kind", [PACS008, PAIN001])
def test_skeleton_validates_against_its_xsd(kind):
    xml = build_message(kind, 1, jobs(), random.Random(1))
    assert validate_xml(kind, xml) == []


@pytest.mark.parametrize("kind", [PACS008, PAIN001])
def test_every_country_validates(kind):
    for code in countries.codes():
        xml = build_message(kind, 1, jobs(code, code), random.Random(1))
        assert validate_xml(kind, xml) == [], code


def test_validation_catches_a_broken_message():
    xml = build_message(PACS008, 1, jobs(), random.Random(1))
    broken = xml.replace(b"<GrpHdr>", b"<GrpHdrX>").replace(b"</GrpHdr>", b"</GrpHdrX>")
    assert validate_xml(PACS008, broken)
    assert validate_xml(PAIN001, xml)  # a pacs.008 is not a valid pain.001


def test_read_jobs_returns_roles_paths_and_lines():
    xml = build_message(PACS008, 3, jobs(), random.Random(1))
    assert read_jobs(xml) == [
        ("Dbtr", "/Document/FIToFICstmrCdtTrf[1]/CdtTrfTxInf[1]/Dbtr[1]/PstlAdr[1]", ["14 Main St", "Dublin 1"]),
        ("Cdtr", "/Document/FIToFICstmrCdtTrf[1]/CdtTrfTxInf[1]/Cdtr[1]/PstlAdr[1]", ["12 Rue des Tilleuls", "69003 Lyon"]),
    ]
    xml = build_message(PAIN001, 3, jobs(), random.Random(1))
    assert [p for _, p, _ in read_jobs(xml)] == [
        "/Document/CstmrCdtTrfInitn[1]/PmtInf[1]/Dbtr[1]/PstlAdr[1]",
        "/Document/CstmrCdtTrfInitn[1]/PmtInf[1]/CdtTrfTxInf[1]/Cdtr[1]/PstlAdr[1]",
    ]


def test_banks_carry_the_country_in_their_bic():
    xml = build_message(PACS008, 1, jobs(), random.Random(1))
    bics = [e.text for e in etree.fromstring(xml).iter("{*}BICFI")]
    assert [b[4:6] for b in bics] == ["IE", "FR"]


def test_non_ascii_text_survives():
    xml = build_message(PACS008, 1, jobs("DE", "FR", ("Müllerstraße 5", "80335 München"), ("Allée Jean Jaurès", "Lyon")), random.Random(1))
    assert read_jobs(xml)[0][2] == ["Müllerstraße 5", "80335 München"] and validate_xml(PACS008, xml) == []


def test_xml_special_characters_are_escaped():
    xml = build_message(PAIN001, 1, jobs(lines_a=("Smith & Sons <Unit 4>", "Cork")), random.Random(1))
    assert read_jobs(xml)[0][2][0] == "Smith & Sons <Unit 4>" and validate_xml(PAIN001, xml) == []


# ---- faults -----------------------------------------------------------------------------------------------------

def test_missing_country_drops_a_country_line():
    assert fault_missing_country(IE) == ["14 Main St", "Dublin 1 D01 K2X7"]


def test_missing_country_strips_a_suffix_and_any_written_form():
    one_line = rec("GB", ["39 Mill Street Oxford OX1 4JB, United Kingdom"], {"TwnNm": "Oxford", "Ctry": "GB"}, ["one_line"])
    assert fault_missing_country(one_line) == ["39 Mill Street Oxford OX1 4JB"]
    us = rec("US", ["Austin, TX 78701 U.S.A."], {"TwnNm": "Austin", "Ctry": "US"})
    assert fault_missing_country(us) == ["Austin, TX 78701"]
    code = rec("IE", ["Cork T12 XY34 IE"], {"TwnNm": "Cork", "Ctry": "IE"})
    assert fault_missing_country(code) == ["Cork T12 XY34"]


def test_missing_country_does_not_apply_without_country_text():
    assert fault_missing_country(rec("IE", ["14 Main St", "Dublin 1"], IE["gold"], ["no_country"])) is None
    assert fault_missing_country(rec("IE", ["14 Main St", "Cork"], IE["gold"])) is None


def test_a_us_state_is_not_mistaken_for_canada():
    us = rec("US", ["Los Angeles, CA 90001", "USA"], {"TwnNm": "Los Angeles", "Ctry": "US"})
    assert fault_missing_country(us) == ["Los Angeles, CA 90001"]
    state_last = rec("US", ["Los Angeles, CA"], {"TwnNm": "Los Angeles", "Ctry": "US"}, ["no_country"])
    assert fault_missing_country(state_last) is None


def test_town_in_line_moves_the_town_up_keeping_order():
    assert fault_town_in_line(IE) == ["14 Main St Dublin 1", "D01 K2X7", "Ireland"]


def test_town_in_line_takes_the_postcode_when_it_comes_first():
    assert fault_town_in_line(FR) == ["12 Rue des Tilleuls 69003 Lyon", "France"]


def test_town_in_line_keeps_a_comma_with_the_town():
    us = rec("US", ["123 Main St", "Austin, TX 78701"], {"TwnNm": "Austin", "Ctry": "US"})
    assert fault_town_in_line(us) == ["123 Main St Austin,", "TX 78701"]


def test_town_in_line_matches_whole_words_only():
    county = rec("GB", ["1 High St", "OX4 9FJ Oxfordshire"], {"TwnNm": "Oxford", "Ctry": "GB"})
    assert fault_town_in_line(county) is None
    both = rec("GB", ["1 High St", "Oxford OX4 9FJ", "Oxfordshire"], {"TwnNm": "Oxford", "Ctry": "GB"})
    assert fault_town_in_line(both) == ["1 High St Oxford", "OX4 9FJ", "Oxfordshire"]


def test_town_in_line_is_not_applicable_on_the_first_line_or_when_too_long():
    assert fault_town_in_line(rec("IE", ["Cork T12 XY34"], {"TwnNm": "Cork", "Ctry": "IE"})) is None
    long = rec("IE", ["A" * 68, "Cork"], {"TwnNm": "Cork", "Ctry": "IE"})
    assert fault_town_in_line(long) is None
    assert fault_town_in_line(rec("IE", ["x", "y"], {"Ctry": "IE"})) is None


def test_too_many_lines_makes_eight_lines_and_keeps_the_text():
    long = rec("IE", ["Unit 4 Block B Docklands Business Park", "Dublin 1 D01 K2X7", "Ireland"],
               {"TwnNm": "Dublin 1", "Ctry": "IE"})
    lines = fault_too_many_lines(long)
    assert len(lines) == MAX_LINES + 1
    assert " ".join(lines) == " ".join(long["raw_lines"])
    assert all(0 < len(line) <= MAX_LINE_LENGTH for line in lines)


def test_too_many_lines_needs_enough_words():
    assert fault_too_many_lines(rec("IE", ["14 Main St", "Cork"], {"TwnNm": "Cork", "Ctry": "IE"})) is None


def test_apply_fault_falls_through_to_one_that_applies():
    short = rec("IE", ["Cork"], {"TwnNm": "Cork", "Ctry": "IE"}, ["no_country"])
    assert apply_fault(short, random.Random(1)) == (None, ["Cork"])
    fault, lines = apply_fault(IE, random.Random(1))
    assert fault in FAULTS and lines != IE["raw_lines"]


def _norm(text):
    # Commas and semicolons are separators, as in the generator tests (tests/helpers.py written_text).
    return " ".join(text.casefold().replace(",", "").replace(";", "").split())


def test_faults_never_change_what_gold_says(records):
    """Over every generated address: after any fault, each non-country gold value is still in the text, the lines are
    legal, and a missing-country fault really removes the country."""
    applied = {f: 0 for f in FAULTS}
    for r in records[:2400]:
        for fault in FAULTS:
            lines = {"missing_country": fault_missing_country, "too_many_lines": fault_too_many_lines,
                     "town_in_line": fault_town_in_line}[fault](r)
            if lines is None:
                continue
            applied[fault] += 1
            text = _norm(" ".join(lines))
            for name, value in r["gold"].items():
                if name != "Ctry":
                    assert _norm(value) in text, (r["id"], fault, name, value, lines)
            assert all(line.strip() and len(line) <= MAX_LINE_LENGTH for line in lines), (r["id"], fault)
            if fault == "too_many_lines":
                assert len(lines) == MAX_LINES + 1
            else:
                assert len(lines) <= MAX_LINES
            if fault == "missing_country":
                # What was removed is exactly one written form of the country, from the end (a street can end with
                # a country word, as in "Rue Anatole France", so the text itself cannot be checked for absence).
                forms = {_norm(f).strip(" .") for f in (*countries.get(r["country"]).country_names, r["country"])}
                before, after = _norm(" ".join(r["raw_lines"])), _norm(" ".join(lines))
                assert before.startswith(after) and before[len(after):].strip(" .") in forms, (r["id"], lines)
    assert all(n > 100 for n in applied.values()), applied


# ---- the sample set ---------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def built(records, seed):
    return build_messages(records[:600], seed, 60)


def test_messages_alternate_types_and_carry_two_jobs(built):
    assert [m.manifest["message_type"] for m in built[:4]] == [PACS008, PAIN001, PACS008, PAIN001]
    assert all(len(m.manifest["jobs"]) == 2 for m in built)
    assert [m.filename for m in built[:2]] == ["pacs008-0001.xml", "pain001-0002.xml"]


def test_no_address_is_used_twice(built):
    ids = [j["record_id"] for m in built for j in m.manifest["jobs"]]
    assert len(ids) == len(set(ids)) == 120


def test_manifest_gold_is_the_records_gold(built, records):
    by_id = {r["id"]: r for r in records}
    for m in built:
        for j in m.manifest["jobs"]:
            r = by_id[j["record_id"]]
            assert j["gold"] == r["gold"] and j["tags"] == r["tags"] and j["difficulty"] == r["difficulty"]
            assert j["country_hint"] == r["country"]


def test_manifest_lines_and_paths_match_the_xml(built):
    for m in built:
        found = read_jobs(m.xml)
        assert [(j["role"], j["xml_path"], j["raw_lines"]) for j in m.manifest["jobs"]] == found


def test_unfaulted_jobs_keep_their_lines(built, records):
    by_id = {r["id"]: r for r in records}
    for m in built:
        for j in m.manifest["jobs"]:
            if j["fault"] is None:
                assert j["raw_lines"] == by_id[j["record_id"]]["raw_lines"]
            else:
                assert j["raw_lines"] != by_id[j["record_id"]]["raw_lines"]


def test_validity_follows_the_faults(built):
    for m in built:
        too_many = any(j["fault"] == "too_many_lines" for j in m.manifest["jobs"])
        assert validate_xml(m.manifest["message_type"], m.xml) == m.manifest["xsd_errors"] + [] or too_many
        assert m.manifest["xsd_valid"] is (not too_many)
        if too_many:
            assert any("AdrLine" in e for e in m.manifest["xsd_errors"])


def test_every_fault_and_some_clean_jobs_appear(built):
    seen = {j["fault"] for m in built for j in m.manifest["jobs"]}
    assert seen == {None, *FAULTS}


def test_build_is_deterministic(records, seed, built):
    again = build_messages(records[:600], seed, 60)
    assert [(m.filename, m.xml, m.manifest) for m in again] == [(m.filename, m.xml, m.manifest) for m in built]
    other = build_messages(records[:600], seed + 1, 60)
    assert [m.xml for m in other] != [m.xml for m in built]


def test_too_few_records_is_an_error(records, seed):
    with pytest.raises(ValueError, match="need 20"):
        build_messages(records[:19], seed, 10)


def test_write_messages_writes_files_and_manifest(tmp_path, built, seed):
    (tmp_path / "stale.xml").write_text("old")
    manifest = write_messages(tmp_path, built, seed, "dev")
    assert not (tmp_path / "stale.xml").exists()
    assert len(list(tmp_path.glob("*.xml"))) == 60 == manifest["messages"]
    on_disk = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert on_disk["jobs"] == 120 and on_disk["files"][0]["file"] == "pacs008-0001.xml"
    assert sum(on_disk["faults"].values()) == sum(1 for m in built for j in m.manifest["jobs"] if j["fault"])


# ---- the committed sample set -----------------------------------------------------------------------------------

def test_committed_messages_come_from_dev_and_reproduce(seed):
    dev = read_jsonl(REPO / "data" / "splits" / "dev.jsonl")
    out = REPO / "data" / "messages"
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["messages"] == 300 and manifest["source_split"] == "dev"
    expected = build_messages(dev, seed, 300)
    assert [m.filename for m in expected] == [f["file"] for f in manifest["files"]]
    for m in expected:
        assert (out / m.filename).read_bytes() == m.xml
    assert manifest["files"] == [m.manifest for m in expected]


def test_committed_messages_validate_except_the_deliberate_faults():
    out = REPO / "data" / "messages"
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    dev_ids = {r["id"] for r in read_jsonl(REPO / "data" / "splits" / "dev.jsonl")}
    for f in manifest["files"]:
        kind = f["message_type"]
        errors = validate_xml(kind, (out / f["file"]).read_bytes())
        assert bool(errors) == any(j["fault"] == "too_many_lines" for j in f["jobs"]), f["file"]
        assert all(j["record_id"] in dev_ids for j in f["jobs"])
    assert manifest["xsd_valid"] == sum(1 for f in manifest["files"] if f["xsd_valid"])


def test_messages_are_built_only_from_dev_gold_keys():
    dev = {gold_key(r) for r in read_jsonl(REPO / "data" / "splits" / "dev.jsonl")}
    manifest = json.loads((REPO / "data" / "messages" / "manifest.json").read_text(encoding="utf-8"))
    for f in manifest["files"]:
        for j in f["jobs"]:
            assert gold_key({"country": j["country"], "gold": j["gold"]}) in dev
