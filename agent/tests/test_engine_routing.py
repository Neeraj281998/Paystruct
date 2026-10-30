import copy
import json
import subprocess
import sys

import pytest
import yaml

from agent.rules.engine import REGISTRY, RulesEngine, load_config
from agent.rules.gazetteer import Gazetteer, Place, fold
from agent.rules.profile import load_profiles
from agent.rules.rule_finalize import LengthRule
from agent.rules.state import ACCEPT, NEEDS_LLM, REVIEW, ParseState, tokenize
from agent.rules.xsd import REPO_ROOT, load_schema

from .conftest import make_gazetteer


# -- routing ---------------------------------------------------------------------------------------------------------
def test_a_clean_address_is_accepted(engine):
    r = engine.parse(["64B Market Square", "Kilkenny R95 NRC2", "Co. Kilkenny", "Ireland"])
    assert r.route == ACCEPT and r.fields["TwnNm"] == "Kilkenny" and r.confidence >= 0.8 and not r.route_reasons


def test_no_town_written_goes_to_review_and_town_stays_unset(engine):
    r = engine.parse(["27 rue des Acacias-Fleuris", "69003", "France"])
    assert r.route == REVIEW and "TwnNm" not in r.fields and "no_town_written" in r.route_reasons


def test_postcode_only_is_never_turned_into_a_town(engine):
    r = engine.parse(["Rabenstieg 3", "20457", "Deutschland"])
    assert r.route == REVIEW and "TwnNm" not in r.fields


def test_contradictory_country_goes_to_review(engine):
    r = engine.parse(["12 Main St", "Bristol BS6 7QD", "Ireland"])
    assert r.route == REVIEW and "country_conflict" in r.flags


def test_a_hint_that_contradicts_the_text_goes_to_review(engine):
    r = engine.parse(["12 Main St", "Cork T12 AC34", "IE"], country_hint="GB")
    assert r.route == REVIEW and r.fields["Ctry"] == "IE"


def test_unknown_country_goes_to_review(engine):
    r = engine.parse(["asdf qwer"])
    assert r.route == REVIEW and "Ctry" not in r.fields


def test_unclaimed_text_needs_the_llm_and_is_reported(engine):
    r = engine.parse(["12 Main St", "mystery words 99", "Cork T12 AC34", "IE"])
    assert r.route == NEEDS_LLM and any("mystery" in l.text for l in r.leftovers) and "unclaimed_text" in r.route_reasons


def test_landmarks_are_reported_but_do_not_block_accept(engine):
    r = engine.parse(["Plot 22, Behind old water tank, Sector 12", "Jaipur, Rajasthan 302021", "India"])
    assert r.route == ACCEPT
    assert [l.text for l in r.leftovers] == ["Behind old water tank"] and r.leftovers[0].reason.startswith("landmark")


def test_leftover_offsets_point_into_the_text(engine):
    r = engine.parse(["12 Main St", "mystery words 99", "Cork T12 AC34", "IE"])
    for l in r.leftovers:
        assert r.text[l.start:l.end] == l.text


def test_partial_postcode_needs_the_llm(engine):
    r = engine.parse(["8 Pellam Street Hackney London E8 UK"])
    assert r.fields.get("PstCd") == "E8" and r.route == NEEDS_LLM


def test_country_from_cues_only_is_not_confident_enough_to_accept(engine):
    r = engine.parse(["Gartestr. 95", "Münster 48079"])
    assert r.fields["Ctry"] == "DE" and r.route == NEEDS_LLM
    assert engine.parse(["Gartestr. 95", "Münster 48079"], country_hint="DE").route == ACCEPT


def test_ctry_is_the_only_value_not_taken_from_the_text(engine):
    r = engine.parse(["Gartestr. 95", "Münster 48079"], country_hint="DE")
    for name, value in r.fields.items():
        if name != "Ctry":
            assert value in r.text


# -- hybrid ----------------------------------------------------------------------------------------------------------
def test_hybrid_keeps_town_and_country_structured_and_the_rest_in_adrline(engine):
    r = engine.parse(["12 Main St", "mystery words 99", "Cork T12 AC34", "IE"])
    assert r.hybrid["TwnNm"] == "Cork" and r.hybrid["Ctry"] == "IE"
    assert all(len(l) <= 70 for l in r.hybrid["AdrLine"]) and len(r.hybrid["AdrLine"]) <= 2
    assert "mystery words 99" in " ".join(r.hybrid["AdrLine"])


def test_hybrid_respects_the_configured_maximum(gaz):
    cfg = load_config()
    cfg["max_adr_lines"] = 1
    e = RulesEngine(config=cfg, gazetteer=gaz)
    r = e.parse(["qwertyuiopasdfghjkl zxcvbnm mnbvcxz", "poiuytrewqlkjhgfdsa zxcvbnm mnbvcxz", "Cork T12 AC34", "IE"])
    assert r.hybrid is None and "hybrid_too_long" in r.flags
    assert RulesEngine(gazetteer=gaz).parse(["qwertyuiopasdfghjkl zxcvbnm mnbvcxz", "poiuytrewqlkjhgfdsa zxcvbnm mnbvcxz", "Cork T12 AC34", "IE"]).hybrid is not None


def test_no_hybrid_without_a_town(engine):
    assert engine.parse(["27 rue des Acacias-Fleuris", "69003", "France"]).hybrid is None


def test_accepted_addresses_have_no_hybrid(engine):
    assert engine.parse(["64B Market Square", "Kilkenny R95 NRC2", "Ireland"]).hybrid is None


# -- length ----------------------------------------------------------------------------------------------------------
def test_a_value_over_the_xsd_maximum_is_dropped_not_truncated(ctx):
    s = ParseState(raw_lines=["x"])
    s.text, s.tokens = tokenize(["Cork " + "a" * 40])
    s.claim("CtrySubDvsn", [1], "t", "w", 0.9)
    s.fields["Ctry"] = "IE"
    out = LengthRule(ctx).apply(s)
    assert "CtrySubDvsn" not in out.fields and "overlong:CtrySubDvsn" in out.flags and out.is_free(1)


def test_a_postcode_over_sixteen_characters_is_dropped(engine):
    r = engine.parse(["12 Main St", "Cork", "T12" + "9" * 20, "Ireland"])
    assert all(len(v) <= load_schema().max_length(k) for k, v in r.fields.items() if load_schema().max_length(k))


# -- the chain -------------------------------------------------------------------------------------------------------
def test_rules_run_in_the_configured_order(gaz):
    cfg = load_config()
    cfg["order"] = ["normalise", "country"]
    r = RulesEngine(config=cfg, gazetteer=gaz).parse(["12 Main St", "Cork T12 AC34", "IE"])
    assert set(r.fields) == {"Ctry"}


def test_every_rule_in_the_default_order_is_registered():
    assert set(load_config()["order"]) == set(REGISTRY)


def test_apply_returns_a_new_state_and_leaves_the_input_alone(ctx):
    s = REGISTRY["normalise"](ctx).apply(ParseState(raw_lines=["12 Main St", "Cork T12 AC34", "IE"]))
    before = copy.deepcopy(s)
    out = REGISTRY["country"](ctx).apply(s)
    assert out is not s and s.fields == before.fields and s.roles == before.roles and out.fields["Ctry"] == "IE"


def test_evidence_and_spans_exist_for_every_output_field(engine):
    r = engine.parse(["Flat 2, 14 Marlow Court", "Bristol BS6 7QD", "UK"])
    for name in r.fields:
        assert r.evidence[name], name
        assert name in r.spans and name in r.field_confidence
    for name, spans in r.spans.items():
        for s, e in spans:
            assert r.text[s:e].strip()


def test_engine_is_deterministic(engine):
    lines = ["Flat 2, 14 Marlow Court", "Bristol BS6 7QD", "UK"]
    assert engine.parse(lines).as_dict() == engine.parse(lines).as_dict()


# -- country profiles are data ---------------------------------------------------------------------------------------
def test_adding_a_country_is_adding_a_file(tmp_path, gaz):
    src = REPO_ROOT / "agent/rules/countries"
    for f in src.glob("*.yaml"):
        (tmp_path / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    lu = yaml.safe_load((src / "NL.yaml").read_text(encoding="utf-8"))
    lu.update({"code": "LU", "names": ["Luxembourg", "Luxemburg"], "postcode": {"patterns": [r"L-\d{4}"], "max_tokens": 1, "unique": True}})
    (tmp_path / "LU.yaml").write_text(yaml.safe_dump(lu, allow_unicode=True), encoding="utf-8")
    profiles = load_profiles(tmp_path)
    assert "LU" in profiles and len(profiles) == 9
    g = make_gazetteer()
    g.add("LU", "Esch", Place("Esch", "LU", "", 30000))
    r = RulesEngine(profiles=profiles, gazetteer=g).parse(["Rue Foo 12", "L-4000 Esch", "Luxembourg"])
    assert r.fields["Ctry"] == "LU" and r.fields["PstCd"] == "L-4000" and r.fields["TwnNm"] == "Esch"


def test_all_eight_profiles_are_present():
    assert sorted(load_profiles(REPO_ROOT / "agent/rules/countries")) == ["CA", "DE", "FR", "GB", "IE", "IN", "NL", "US"]


# -- gazetteer -------------------------------------------------------------------------------------------------------
def test_fold_ignores_case_accents_and_punctuation():
    assert fold("Köln") == fold("KOLN") == "koln"
    assert fold("St. John's") == fold("st johns")
    assert fold("München-Haidhausen") == "munchen haidhausen"


def test_gazetteer_lookup_is_per_country():
    g = Gazetteer()
    g.add("FR", "Paris", Place("Paris", "FR", "11", 2000000))
    g.add("US", "Paris", Place("Paris", "US", "TX", 25000))
    assert g.lookup("FR", "PARIS").population == 2000000 and g.lookup("US", "paris").admin1 == "TX" and g.lookup("DE", "Paris") is None
    assert g.admin1_codes("US", "Paris") == {"TX"}


def test_the_real_gazetteer_loads_when_present():
    from agent.rules.gazetteer import GAZETTEER_PATH, load
    if not GAZETTEER_PATH.exists():
        pytest.skip("cities500.txt is not downloaded")
    g = load(countries={"FR", "DE"})
    assert g.lookup("FR", "Marseille") is not None and g.lookup("DE", "Köln") is not None


# -- cli -------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("split", ["test", "hard", "whatever"])
def test_cli_refuses_everything_but_dev_and_calibration(split):
    p = subprocess.run([sys.executable, "-m", "agent.rules.cli", "--split", split], capture_output=True, text=True, cwd=REPO_ROOT)
    assert p.returncode == 2 and "REFUSED" in p.stderr and p.stdout == ""


def test_cli_never_opens_the_test_or_hard_files():
    import inspect
    from agent.rules import cli
    assert "test.jsonl" not in inspect.getsource(cli) and "hard.jsonl" not in inspect.getsource(cli)
    with pytest.raises(SystemExit):
        cli.load_split("test")
    with pytest.raises(SystemExit):
        cli.load_split("hard")
