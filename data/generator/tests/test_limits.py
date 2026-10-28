from __future__ import annotations

import re

from addrgen.limits import GOLD_FIELDS, LIMITS, PACS008_XSD, PAIN001_XSD, REPO_ROOT, load_limits


def _decision_record_table() -> dict[str, int | None]:
    """Element -> maximum length, as recorded in docs/decisions/xsd-versions.md."""
    table = {}
    for line in (REPO_ROOT / "docs" / "decisions" / "xsd-versions.md").read_text().splitlines():
        m = re.match(r"^\| `(\w+)` \| [^|]+ \| ([^|]+) \|", line)
        if m:
            length = m.group(2).strip()
            table[m.group(1)] = None if length == "n/a" else int(length.split()[0])
    return table


def test_both_suppliedxsds_define_the_same_address_elements():
    assert load_limits(PACS008_XSD) == load_limits(PAIN001_XSD)


def test_limits_match_the_decision_record():
    recorded = _decision_record_table()
    assert set(recorded) == set(LIMITS)
    for name, limit in LIMITS.items():
        expected = limit.max_length
        if name == "Ctry":  # recorded as 2: the XSD gives the pattern [A-Z]{2,2}
            assert limit.pattern == "[A-Z]{2,2}"
            expected = 2
        assert recorded[name] == expected, name


def test_the_xsd_wins_over_the_spec_table():
    # The spec table (written for PostalAddress24) says 70, 35, 35, 35, 35.
    for name in ("StrtNm", "BldgNm", "TwnNm", "TwnLctnNm", "DstrctNm"):
        assert LIMITS[name].max_length == 140
    assert LIMITS["AdrLine"].max_length == 70 and LIMITS["AdrLine"].max_occurs == 7


def test_gold_fields_are_the_v1_fields_in_xsd_order():
    assert list(GOLD_FIELDS) == [n for n in LIMITS if n in GOLD_FIELDS]
    assert set(GOLD_FIELDS) == {"StrtNm", "BldgNb", "BldgNm", "Flr", "Room", "PstBx", "PstCd", "TwnNm", "TwnLctnNm",
                                "CtrySubDvsn", "Ctry"}
    for unused in ("Dept", "SubDept", "UnitNb", "DstrctNm", "CareOf"):
        assert unused not in GOLD_FIELDS
