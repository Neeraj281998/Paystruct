from __future__ import annotations

import copy

from addrgen.validate import check_record

GOOD = {"id": "ie-00042", "country": "IE", "difficulty": "hard", "tags": ["no_street_number", "postal_district"],
        "raw_lines": ["Unit 4 Block B Docklands Business Park", "Dublin 1 D01 K2X7 Ireland"],
        "gold": {"BldgNm": "Block B Docklands Business Park", "Room": "Unit 4", "PstCd": "D01 K2X7",
                 "TwnNm": "Dublin 1", "Ctry": "IE"}}


def bad(**changes):
    rec = copy.deepcopy(GOOD)
    for key, value in changes.items():
        if key == "gold":
            rec["gold"] = value
        else:
            rec[key] = value
    return check_record(rec)


def test_the_spec_example_is_valid():
    assert check_record(GOOD) == []


def test_a_gold_value_over_its_xsd_maximum_is_rejected():
    assert any("BldgNb" in p for p in bad(gold={**GOOD["gold"], "BldgNb": "1" * 17}))
    assert any("StrtNm" in p for p in bad(gold={**GOOD["gold"], "StrtNm": "S" * 141}))
    assert not any("StrtNm" in p for p in bad(gold={"StrtNm": "S" * 140, "Ctry": "IE"}))  # 140 is fine: the XSD, not the spec table


def test_a_bad_country_code_is_rejected():
    assert any("Ctry" in p for p in bad(gold={**GOOD["gold"], "Ctry": "Ireland"}))
    assert any("Ctry" in p for p in bad(gold={**GOOD["gold"], "Ctry": "ie"}))


def test_unused_or_unknown_elements_are_rejected():
    assert any("UnitNb" in p for p in bad(gold={**GOOD["gold"], "UnitNb": "4"}))
    assert any("Nope" in p for p in bad(gold={**GOOD["gold"], "Nope": "x"}))


def test_raw_line_limits():
    assert any("71" in p or "over 70" in p for p in bad(raw_lines=["x" * 71]))
    assert any("raw lines" in p for p in bad(raw_lines=["a"] * 8))
    assert any("blank" in p for p in bad(raw_lines=["a", "  "]))


def test_a_po_box_address_has_no_street():
    assert any("PO box" in p for p in bad(gold={**GOOD["gold"], "PstBx": "PO Box 1", "StrtNm": "Main Street"}))


def test_gold_must_be_in_xsd_order_and_have_single_spaces():
    assert any("order" in p for p in bad(gold=dict(reversed(list(GOOD["gold"].items())))))
    assert any("double space" in p for p in bad(gold={**GOOD["gold"], "TwnNm": "Dublin  1"}))


def test_tags_and_difficulty_must_be_well_formed():
    assert any("tags" in p for p in bad(tags=["b", "a"]))
    assert any("difficulty" in p for p in bad(difficulty="impossible"))
