"""Properties every generated record must have, checked over 1,800 records."""
from __future__ import annotations

import re
from collections import Counter

import pytest

from addrgen import countries
from addrgen.countries import gb, ie
from addrgen.difficulty import difficulty_of
from addrgen.limits import GOLD_FIELDS, LIMITS, MAX_LINE_LENGTH, MAX_LINES
from addrgen.validate import check_record
from addrgen.words import BUILDING_PHRASES, BUILDING_WORDS, ROOM_KEYWORDS, STREET_WORDS
from tests.helpers import tokens, written_text


def test_every_record_passes_the_validator(records):
    for rec in records:
        assert check_record(rec) == [], rec["id"]


def test_gold_lengths_are_within_the_xsd_limits(records):
    for rec in records:
        for name, value in rec["gold"].items():
            limit = LIMITS[name]
            assert name in GOLD_FIELDS
            if limit.max_length is not None:
                assert len(value) <= limit.max_length, (rec["id"], name, value)
        assert re.fullmatch(LIMITS["Ctry"].pattern, rec["gold"]["Ctry"])


def test_every_raw_line_is_at_most_70_characters_and_there_are_at_most_7(records):
    assert MAX_LINE_LENGTH == 70 and MAX_LINES == 7
    for rec in records:
        assert 1 <= len(rec["raw_lines"]) <= 7, rec["id"]
        for line in rec["raw_lines"]:
            assert len(line) <= 70, (rec["id"], line)


def test_the_over_70_character_path_is_exercised(records):
    assert sum("long_line_split" in r["tags"] for r in records) >= 5


def test_ids_are_unique_and_in_the_record_format(records):
    ids = [r["id"] for r in records]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"(ie|gb)-\d{5}", i) for i in ids)
    for rec in records:  # the spec's record format, plus the optional country_hint last
        assert list(rec) in (["id", "country", "difficulty", "tags", "raw_lines", "gold"],
                             ["id", "country", "difficulty", "tags", "raw_lines", "gold", "country_hint"])


def test_gold_is_traceable_to_the_raw_text(records):
    """Every gold value except the country code appears in the raw text exactly as written (case and spacing),
    allowing for line breaks and commas."""
    for rec in records:
        text = written_text(rec)
        for name, value in rec["gold"].items():
            if name != "Ctry":
                assert value in text, (rec["id"], name, value, rec["raw_lines"])


def test_no_raw_token_is_unexplained_and_the_country_is_only_the_country(records):
    """Raw tokens = gold tokens + the country as written (code or name), or nothing when there is no country.
    Nothing is dropped, invented or left unlabelled."""
    for rec in records:
        module = countries.get(rec["country"])
        raw = tokens(written_text(rec))
        gold = Counter(tok for name, value in rec["gold"].items() if name != "Ctry" for tok in value.split())
        assert not (gold - raw), (rec["id"], "gold token missing from raw")
        rest = raw - gold
        if "no_country" in rec["tags"]:
            assert not rest, (rec["id"], dict(rest))
        else:
            allowed = [Counter(w.split()) for w in (module.code, *module.country_names)]
            allowed += [Counter(w.upper().split()) for w in (module.code, *module.country_names)]
            assert rest in allowed, (rec["id"], dict(rest))


def test_country_hint_exists_exactly_when_the_country_is_absent(records):
    for rec in records:
        assert ("country_hint" in rec) == ("no_country" in rec["tags"]), rec["id"]
        if "country_hint" in rec:
            assert rec["country_hint"] == rec["country"] == rec["gold"]["Ctry"]


def test_difficulty_is_computed_from_the_tags(records):
    for rec in records:
        assert difficulty_of(set(rec["tags"])) == rec["difficulty"], rec["id"]


def test_tiers_and_countries_are_balanced(records):
    counts = Counter((r["country"], r["difficulty"]) for r in records)
    assert set(counts.values()) == {300}


def test_every_tag_in_the_guide_that_the_generator_makes_appears(records):
    seen = {t for r in records for t in r["tags"]}
    expected = {"no_street_number", "postal_district", "flat", "building_name", "floor", "po_box", "county", "locality",
                "no_country", "country_name", "all_caps", "extra_spaces", "one_line", "missing_commas", "reordered",
                "postcode_split", "postcode_no_space", "postcode_wrong_line", "typo", "abbreviated", "long_line_split"}
    assert expected <= seen, expected - seen


def test_typo_rate_is_controlled(records):
    hard = [r for r in records if r["difficulty"] == "hard"]
    share = sum("typo" in r["tags"] for r in hard) / len(hard)
    assert 0.18 <= share <= 0.32  # the default rate is 0.25 of hard records
    assert not any("typo" in r["tags"] for r in records if r["difficulty"] != "hard")


# ---- tags mean what they say ------------------------------------------------------------------------------------
def test_tag_semantics(records):
    for rec in records:
        tags, raw, gold, lines = set(rec["tags"]), "\n".join(rec["raw_lines"]), rec["gold"], rec["raw_lines"]
        if "all_caps" in tags:
            assert raw == raw.upper(), rec["id"]
        if "missing_commas" in tags:
            assert "," not in raw, rec["id"]
        if "one_line" in tags:
            assert len(lines) == 1 or "long_line_split" in tags, rec["id"]
        if "extra_spaces" in tags:
            assert any("  " in l or l != l.strip() for l in lines), rec["id"]
        if "postcode_no_space" in tags:
            assert " " not in gold["PstCd"], rec["id"]
        elif "PstCd" in gold:
            assert gold["PstCd"].count(" ") == 1, rec["id"]
        if "abbreviated" in tags:
            words = {w.rstrip(".").upper() for f in ("StrtNm", "Room") if f in gold for w in gold[f].split()}
            assert words & {"ST", "RD", "AVE", "DR", "LN", "TER", "CL", "SQ", "GDNS", "CRES", "APT"}, rec["id"]
        if "no_street_number" in tags:
            assert "BldgNb" not in gold and ("StrtNm" in gold or "BldgNm" in gold), rec["id"]
        if "po_box" in tags:
            assert "PstBx" in gold and "StrtNm" not in gold and "BldgNb" not in gold, rec["id"]
        if "county" in tags:
            assert "CtrySubDvsn" in gold
        if "postal_district" in tags:
            assert rec["country"] == "IE" and re.fullmatch(r"(?i)dublin \d+w?", gold["TwnNm"]), rec["id"]
        if "postcode_split" in tags:
            a, b = gold["PstCd"].split(" ")
            first = next(i for i, l in enumerate(lines) if l.strip().rstrip(",").rstrip().upper().endswith(a.upper()))
            assert lines[first + 1].strip().upper().startswith(b.upper()), rec["id"]
        if "postcode_wrong_line" in tags:
            first_half = gold["PstCd"].split(" ")[0]  # a long line may be wrapped through the postcode itself
            pc_line = next(l for l in lines if first_half in l.split())
            assert gold["TwnNm"] not in pc_line, rec["id"]


# ---- the guide's labelling decisions hold, and typos never reach towns, postcodes or countries --------------------
_IE_TOWNS = {t.casefold() for t, *_ in ie.TOWNS} | {d.casefold() for d, _ in ie.DUBLIN_DISTRICTS}
_GB_TOWNS = {t.casefold() for t, *_ in gb.POST_TOWNS}
_EIRCODE = re.compile(r"^([ACDEFHKNPRTVWXY][0-9]{2}|D6W)")
_GB_POSTCODE = re.compile(r"^[A-Z]{1,2}[0-9][0-9A-Z]? ?[0-9][A-Z]{2}$")


def test_towns_postcodes_and_countries_are_never_corrupted(records):
    for rec in records:
        gold = rec["gold"]
        if rec["country"] == "IE":
            assert gold["TwnNm"].casefold() in _IE_TOWNS, (rec["id"], gold["TwnNm"])
            assert _EIRCODE.match(gold["PstCd"].upper()), (rec["id"], gold["PstCd"])
        else:
            assert gold["TwnNm"].casefold() in _GB_TOWNS, (rec["id"], gold["TwnNm"])
            assert _GB_POSTCODE.match(gold["PstCd"].upper()), (rec["id"], gold["PstCd"])
        assert gold["Ctry"] == rec["country"]


def test_a_locality_is_only_ever_beside_a_town_it_belongs_to(records):
    """Fixes 'Knocknacarra beside Drogheda': every TwnLctnNm must be listed under that record's own town."""
    by_town = {"IE": ie.LOCALITIES_BY_TOWN, "GB": gb.LOCALITIES_BY_TOWN}
    checked = 0
    for rec in records:
        gold = rec["gold"]
        if "TwnLctnNm" in gold:
            checked += 1
            allowed = by_town[rec["country"]][gold["TwnNm"].casefold()]
            assert gold["TwnLctnNm"].casefold() in allowed, (rec["id"], gold["TwnLctnNm"], gold["TwnNm"])
    assert checked > 100  # the check is exercised, not vacuous


def test_labelling_guide_conventions(records):
    street_words = {w.casefold() for w in STREET_WORDS}
    building_words = {w.casefold() for w in BUILDING_WORDS} | {p.casefold() for p in BUILDING_PHRASES}
    for rec in records:
        gold = rec["gold"]
        if "StrtNm" in gold:  # section 3: a street ends in a street word, which a typo never touches
            assert gold["StrtNm"].split()[-1].rstrip(".").casefold() in street_words, (rec["id"], gold["StrtNm"])
        if "BldgNm" in gold:
            assert any(w in gold["BldgNm"].casefold() for w in building_words), (rec["id"], gold["BldgNm"])
        if "Room" in gold:  # section 2: flats, units, apartments and rooms keep their keyword
            assert gold["Room"].split()[0].rstrip(".").casefold() in {k.casefold() for k in ROOM_KEYWORDS}, rec["id"]
        if "Flr" in gold:
            assert re.fullmatch(r"(?i)(ground floor|basement|floor \d|\d(st|nd|rd|th) floor)", gold["Flr"]), rec["id"]
        if "PstBx" in gold:  # section 7
            assert re.fullmatch(r"(?i)(PO|P\.O\.) Box \d+", gold["PstBx"]), rec["id"]
        if "BldgNb" in gold:
            assert re.fullmatch(r"\d+[A-D]?(-\d+)?", gold["BldgNb"]), rec["id"]
        if "CtrySubDvsn" in gold and rec["country"] == "IE":  # section 4: county as written
            assert re.fullmatch(r"(?i)(co\.|county) [a-z]+", gold["CtrySubDvsn"]), rec["id"]
        if rec["country"] == "IE" and "TwnNm" in gold and gold["TwnNm"].casefold().startswith("dublin "):
            assert "DstrctNm" not in gold  # section 1: the district stays with the town
