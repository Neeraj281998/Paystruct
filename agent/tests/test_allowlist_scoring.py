import pytest

from agent.rules import allowlist
from agent.rules.scoring import normalise, score_record, values_equal


def test_normalise_follows_guide_section_10():
    assert normalise("  Main   STREET ,. ", "StrtNm") == "main street"
    assert normalise("D01 K2X7", "PstCd") == normalise("d01k2x7", "PstCd") == "d01k2x7"
    assert normalise("Café", "TwnNm") == normalise("Café", "TwnNm")
    assert normalise("Dún", "TwnNm") != normalise("Dun", "TwnNm")  # accents are kept


def test_whitespace_is_removed_only_for_postcodes():
    assert normalise("a  b", "StrtNm") == "a b"
    assert normalise("a  b", "PstCd") == "ab"


def test_allowlisted_pairs_are_equal():
    assert values_equal("Main St", "Main Street", "StrtNm", "IE")
    assert values_equal("Hauptstr.", "Hauptstraße", "StrtNm", "DE") and values_equal("Hauptstr.", "Hauptstrasse", "StrtNm", "DE")
    assert values_equal("Bd Voltaire", "Boulevard Voltaire", "StrtNm", "FR")
    assert values_equal("N Main St", "North Main Street", "StrtNm", "US")
    assert values_equal("Apt 5", "Apartment 5", "Room", "US")


def test_pairs_are_per_country():
    assert not values_equal("Av Foch", "Avenue Foch", "StrtNm", "DE")
    assert not values_equal("Bd Voltaire", "Boulevard Voltaire", "StrtNm", "IE")
    assert not values_equal("Main St", "Main Road", "StrtNm", "IE")


def test_postcode_and_country_ignore_the_allowlist():
    assert not values_equal("D01 K2X7", "D01 K2X8", "PstCd", "IE")
    assert not values_equal("IE", "GB", "Ctry", "IE")


def test_exact_match_needs_every_gold_field_and_no_extra_field():
    gold = {"StrtNm": "Main St", "BldgNb": "14", "TwnNm": "Cork", "Ctry": "IE"}
    assert score_record(dict(gold), gold, "IE").exact
    assert score_record({**gold, "StrtNm": "MAIN STREET"}, gold, "IE").exact
    extra = score_record({**gold, "PstCd": "T12 AB34"}, gold, "IE")
    assert not extra.exact and extra.extra == ["PstCd"]
    missing = score_record({k: v for k, v in gold.items() if k != "BldgNb"}, gold, "IE")
    assert not missing.exact and missing.missing == ["BldgNb"] and len(missing.matched) == 3
    wrong = score_record({**gold, "TwnNm": "Cobh"}, gold, "IE")
    assert wrong.wrong == ["TwnNm"] and wrong.pattern() == "TwnNm:wrong"


def test_unknown_output_fields_are_not_counted():
    gold = {"TwnNm": "Cork", "Ctry": "IE"}
    assert score_record({**gold, "AdrLine": "x"}, gold, "IE").exact


def test_allowlist_module_has_no_imports_beyond_the_standard_library():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(allowlist))
    imported = {n.names[0].name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)} | \
               {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert imported <= {"__future__", "unicodedata"}


@pytest.mark.parametrize("country", ["IE", "GB", "FR", "DE", "NL", "CA", "US", "IN"])
def test_every_country_has_an_entry(country):
    assert country in allowlist.ABBREVIATIONS
