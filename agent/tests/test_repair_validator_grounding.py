import pytest

from agent.repair import grounding, support
from agent.repair.iso3166 import ALPHA2
from agent.repair.jsonschema_lite import validate as schema_validate
from agent.repair.tools import ADDRESS_FIELDS, SUBMIT_SCHEMA, TOOL_SPECS, AttemptContext, country_lookup
from agent.repair.validator import (ADDR_UNSTRUCTURED, FIELD_TOO_LONG, HYBRID_DUPLICATION, HYBRID_LINES_EXCEEDED, INVALID_CTRY, MISSING_CTRY,
                                    MISSING_TWNNM, POSTCODE_FORMAT, Candidate, max_adr_lines, validate)
from agent.rules.engine import RulesEngine
from agent.rules.profile import all_profiles

from .conftest import make_gazetteer

GAZ = make_gazetteer()


def c(**f):
    lines = f.pop("AdrLine", [])
    return Candidate(f, lines)


# -- validator: one test per code -----------------------------------------------------------------------------------------
def test_a_good_address_is_valid():
    assert validate(c(TwnNm="Cork", Ctry="IE", PstCd="T12 AC34", StrtNm="Main St")) == []


def test_nothing_at_all_is_unstructured():
    assert validate(Candidate()) == [ADDR_UNSTRUCTURED]


def test_missing_town_and_country():
    assert validate(c(StrtNm="Main St")) == [MISSING_TWNNM, MISSING_CTRY]


def test_no_town_is_not_special_cased():
    # a no-town address simply has no TwnNm; the validator reports it and the pipeline routes it to REVIEW
    assert MISSING_TWNNM in validate(c(Ctry="FR", PstCd="69003", StrtNm="rue des Acacias"))


@pytest.mark.parametrize("code,bad", [("ZZ", True), ("XX", True), ("ie", True), ("IE", False), ("FR", False), ("KP", False), ("I", True)])
def test_iso_country_codes(code, bad):
    assert (INVALID_CTRY in validate(c(TwnNm="X", Ctry=code))) == bad


def test_the_iso_table_has_the_assigned_codes():
    assert len(ALPHA2) == 249 and {"IE", "GB", "FR", "DE", "NL", "CA", "US", "IN"} <= ALPHA2


def test_field_limits_come_from_the_xsd():
    assert FIELD_TOO_LONG in validate(c(TwnNm="Cork", Ctry="IE", BldgNb="1" * 17))
    assert FIELD_TOO_LONG not in validate(c(TwnNm="Cork", Ctry="IE", BldgNb="1" * 16))
    assert FIELD_TOO_LONG in validate(c(TwnNm="Cork", Ctry="IE", StrtNm="x" * 141))
    assert FIELD_TOO_LONG in validate(c(TwnNm="Cork", Ctry="IE", CtrySubDvsn="x" * 36))
    assert FIELD_TOO_LONG in validate(c(TwnNm="Cork", Ctry="IE", AdrLine=["x" * 71]))


@pytest.mark.parametrize("country,pc,ok", [("IE", "T12 AC34", True), ("IE", "T12 ZZ99", False), ("GB", "BS6 7QD", True), ("GB", "12345", False),
                                           ("US", "30317-2153", True), ("US", "3031", False), ("NL", "1015 CJ", True), ("CA", "H3A 0P8", True),
                                           ("FR", "7500", False), ("IN", "411 001", True)])
def test_postcode_format_follows_the_country_profile(country, pc, ok):
    assert (POSTCODE_FORMAT not in validate(c(TwnNm="X", Ctry=country, PstCd=pc))) == ok


def test_hybrid_line_limit_is_the_existing_config_value():
    n = max_adr_lines()
    assert n == 2   # placeholder; the real CBPR+ limit must be confirmed (docs/decisions/hybrid-address.md)
    assert HYBRID_LINES_EXCEEDED not in validate(c(TwnNm="Cork", Ctry="IE", AdrLine=["a b", "c d"]))
    assert HYBRID_LINES_EXCEEDED in validate(c(TwnNm="Cork", Ctry="IE", AdrLine=["a", "b", "c"]))
    assert HYBRID_LINES_EXCEEDED not in validate(c(TwnNm="Cork", Ctry="IE", AdrLine=["a", "b", "c"]), max_lines=3)


def test_hybrid_may_not_repeat_a_structured_value():
    assert HYBRID_DUPLICATION in validate(c(TwnNm="Cork", Ctry="IE", AdrLine=["12 Main St, Cork"]))
    assert HYBRID_DUPLICATION not in validate(c(TwnNm="Cork", Ctry="IE", AdrLine=["12 Main St"]))


# -- grounding -----------------------------------------------------------------------------------------------------------
RAW = ["14 Main St,", "Cork  T12 AC34", "IE"]


def g(cand, raw=RAW, hint=None, rules=None, gaz=GAZ):
    return grounding.check(cand, raw, hint, rules, gaz)


def test_values_copied_from_the_input_are_grounded():
    assert g(c(BldgNb="14", StrtNm="Main St", TwnNm="Cork", PstCd="T12 AC34", Ctry="IE")).ok


def test_normalisation_covers_case_whitespace_and_allowed_punctuation():
    assert g(c(StrtNm="MAIN ST", TwnNm="cork", PstCd="t12ac34", Ctry="IE")).ok


@pytest.mark.parametrize("name,value", [("TwnNm", "Dublin"), ("PstCd", "T12 AC35"), ("StrtNm", "Main Road"), ("BldgNb", "15"), ("CtrySubDvsn", "Co. Cork")])
def test_an_invented_value_is_ungrounded(name, value):
    res = g(Candidate({**{"TwnNm": "Cork", "Ctry": "IE"}, name: value}))
    assert f"UNGROUNDED_VALUE:{name}" in res.reasons


def test_allowlisted_expansions_are_the_only_exception():
    assert g(c(StrtNm="Main Street", TwnNm="Cork", Ctry="IE")).ok
    assert not g(c(StrtNm="Main Avenue", TwnNm="Cork", Ctry="IE")).ok


def test_words_from_different_places_do_not_make_a_value():
    # "Cork Main" never occurs contiguously in the input
    assert "UNGROUNDED_VALUE:StrtNm" in g(c(StrtNm="Cork Main", TwnNm="Cork", Ctry="IE")).reasons


def test_adrlines_must_be_grounded_too():
    assert g(c(TwnNm="Cork", Ctry="IE", AdrLine=["14 Main St"])).ok
    assert grounding.UNGROUNDED_ADRLINE in g(c(TwnNm="Cork", Ctry="IE", AdrLine=["99 Elm Street"])).reasons


@pytest.mark.parametrize("raw,hint,code,ok", [
    (["12 Main St", "Cork T12 AC34", "Ireland"], None, "IE", True),
    (["12 Main St", "Cork"], "IE", "IE", True),
    (["12 Main St", "Bristol BS6 7QD"], None, "GB", True),          # postcode pattern unique to one country
    (["12 Main St", "Cork"], None, "IE", False),                    # nothing in the text says Ireland
    (["12 Main St", "Cork T12 AC34", "IE"], None, "GB", False),
    (["12 Rue X", "75008 Paris"], None, "FR", False),               # a 5-digit postcode belongs to several countries
    (["somewhere", "Eire"], None, "IE", True),
])
def test_the_country_must_be_derivable_from_the_text(raw, hint, code, ok):
    assert grounding.country_derivable(code, raw, hint) == ok


def test_an_underivable_country_is_ungrounded_country():
    assert grounding.UNGROUNDED_COUNTRY in g(c(TwnNm="Cork", Ctry="IE"), raw=["12 Main St", "Cork"]).reasons
    assert grounding.UNGROUNDED_COUNTRY not in g(c(TwnNm="Cork", Ctry="IE"), raw=["12 Main St", "Cork"], hint="IE").reasons


def test_agreement_with_explicit_rules_fields():
    engine = RulesEngine(gazetteer=GAZ)
    rules = engine.parse(["14 Main St", "Cork T12 AC34", "IE"])
    assert g(c(TwnNm="Cork", PstCd="T12 AC34", Ctry="IE"), rules=rules).ok
    other = grounding.check(c(TwnNm="Cork", PstCd="T12 AD34", Ctry="IE"), ["14 Main St", "Cork T12 AC34 T12 AD34", "IE"], None, rules, GAZ)
    assert "CONTRADICTS_RULES:PstCd" in other.reasons
    assert "CONTRADICTS_RULES:TwnNm" in grounding.check(c(TwnNm="Galway", PstCd="T12 AC34", Ctry="IE"), ["14 Main St", "Cork Galway T12 AC34", "IE"], None, rules, GAZ).reasons
    # leaving out the postcode of a structured address is also a contradiction
    assert "CONTRADICTS_RULES:PstCd" in g(c(TwnNm="Cork", Ctry="IE"), rules=rules).reasons


def test_a_written_town_must_exist_in_the_gazetteer():
    assert grounding.TOWN_NOT_IN_GAZETTEER in grounding.check(c(TwnNm="Ballyvaughan", Ctry="IE"), ["Ballyvaughan", "IE"], None, None, GAZ).reasons
    assert grounding.check(c(TwnNm="Dublin 16", Ctry="IE"), ["Dublin 16", "IE"], None, None, GAZ).ok   # a written district stays with the town


def test_without_a_gazetteer_the_check_is_skipped_and_marked_unchecked():
    from agent.rules.gazetteer import Gazetteer
    res = grounding.check(c(TwnNm="Cork", Ctry="IE"), RAW, None, None, Gazetteer())
    assert res.ok and res.unchecked
    assert grounding.check(c(TwnNm="Cork", Ctry="IE"), RAW, None, None, GAZ).unchecked is False


# -- support (explicit evidence vs elimination) ------------------------------------------------------------------------------
@pytest.mark.parametrize("name,value,ok", [
    ("PstCd", "T12 AC34", True), ("PstCd", "ABC", False), ("TwnNm", "Cork", True), ("TwnNm", "Zorbleville", False),
    ("Room", "Flat 3", True), ("Room", "Rm 12", False), ("Flr", "2nd Floor", True), ("PstBx", "PO Box 12", True),
    ("BldgNb", "14", True), ("BldgNb", "14B", True), ("BldgNb", "Blue", False), ("BldgNm", "Marlow Court", True), ("BldgNm", "Mulberry Hall", False),
    ("StrtNm", "Main St", True), ("StrtNm", "Zorble", False), ("StrtNm", "Prinsengracht 263-II", False), ("StrtNm", "5th Main Road", True),
    ("CtrySubDvsn", "Co. Cork", True), ("CtrySubDvsn", "Cork", False), ("TwnLctnNm", "Templeogue", True), ("TwnLctnNm", "The Old Creamery", False),
])
def test_field_support_uses_the_rules_standard(name, value, ok):
    prof = all_profiles()["IE"]
    assert (support.field_support(name, value, "IE", prof, GAZ) == support.EXPLICIT) == ok


def test_support_is_unchecked_for_a_town_when_the_gazetteer_is_missing():
    from agent.rules.gazetteer import Gazetteer
    assert support.field_support("TwnNm", "Cork", "IE", all_profiles()["IE"], Gazetteer()) == support.UNCHECKED


# -- tools ---------------------------------------------------------------------------------------------------------------
def test_the_model_has_exactly_four_tools_and_none_approves_or_publishes():
    names = {t["name"] for t in TOOL_SPECS}
    assert names == {"parse_address", "country_lookup", "validate_candidate", "submit_repair"}
    for bad in ("approve", "publish", "queue", "write", "send"):
        assert not any(bad in n for n in names)
    for t in TOOL_SPECS:
        assert t["input_schema"]["additionalProperties"] is False and t["input_schema"]["type"] == "object"


def test_country_lookup_is_a_static_table_and_never_guesses():
    assert country_lookup("Ireland") == {"code": "IE", "confidence": 1.0}
    assert country_lookup("deutschland")["code"] == "DE" and country_lookup("Éire")["code"] == "IE" and country_lookup("Spain")["code"] == "ES"
    assert country_lookup("Atlantis") == {"code": None, "confidence": 0.0}
    assert country_lookup("Cork") == {"code": None, "confidence": 0.0}


def _ctx():
    return AttemptContext(["14 Main St", "Cork T12 AC34", "IE"], None, RulesEngine(gazetteer=GAZ))


def test_parse_address_returns_fields_and_rule_ids():
    ctx = _ctx()
    out = ctx.run("parse_address", {"lines": ctx.raw_lines})
    assert out["fields"]["TwnNm"] == "Cork" and "postcode" in out["evidence_rule_ids"]["PstCd"] and "postcode" in ctx.returned_rule_ids
    assert "rules_confidence" in out and "leftover_text" in out


def test_validate_candidate_tool_runs_the_validator_and_grounding():
    ctx = _ctx()
    assert ctx.run("validate_candidate", {"address": {"TwnNm": "Cork", "Ctry": "IE"}})["pass"] is True
    bad = ctx.run("validate_candidate", {"address": {"TwnNm": "Dublin", "Ctry": "IE"}})
    assert bad["pass"] is False and "UNGROUNDED_VALUE:TwnNm" in bad["reasons"]


def test_submit_repair_is_schema_checked_and_citation_guarded():
    ctx = _ctx()
    ctx.run("parse_address", {"lines": ctx.raw_lines})
    ok = {"address": {"TwnNm": "Cork", "Ctry": "IE"}, "confidence": 0.9, "rationale": "r", "evidence_rules": ["postcode"]}
    assert ctx.run("submit_repair", dict(ok, evidence_rules=["made_up"]))["accepted_for_verification"] is False
    assert "citation guard" in ctx.submit_error[0]
    assert ctx.run("submit_repair", dict(ok, confidence=2))["accepted_for_verification"] is False
    assert ctx.run("submit_repair", dict(ok, evidence_rules=[]))["accepted_for_verification"] is False
    assert ctx.run("submit_repair", dict(ok, address={"Bogus": "x"}))["accepted_for_verification"] is False
    assert ctx.run("submit_repair", dict(ok, extra=1))["accepted_for_verification"] is False
    assert ctx.run("submit_repair", ok)["accepted_for_verification"] is True and ctx.submitted == ok


def test_unknown_tools_and_bad_arguments_are_errors_not_exceptions():
    ctx = _ctx()
    assert "error" in ctx.run("approve_payment", {"id": 1})
    assert "error" in ctx.run("parse_address", {"lines": "not a list"})
    assert "error" in ctx.run("country_lookup", "text")


def test_schema_lite():
    assert schema_validate({"a": 1}, {"type": "object", "properties": {"a": {"type": "integer"}}, "required": ["a"], "additionalProperties": False}) == []
    assert schema_validate({"a": True}, {"type": "object", "properties": {"a": {"type": "integer"}}})
    assert schema_validate([], {"type": "array", "minItems": 1})
    assert set(SUBMIT_SCHEMA["required"]) == {"address", "confidence", "rationale", "evidence_rules"}
    assert set(ADDRESS_FIELDS) <= set(SUBMIT_SCHEMA["properties"]["address"]["properties"])
