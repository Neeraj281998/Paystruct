"""Fix 1 to 5 of the first-real-run diagnosis: no silent loss of text, locked rules fields, hybrid -> REVIEW, the model is skipped
when it cannot add evidence. Written from the descriptions, before the code."""
from hypothesis import HealthCheck, given, settings, strategies as st

from agent.repair import grounding
from agent.repair.pipeline import REVIEW
from agent.repair.validator import Candidate
from agent.rules.engine import RulesEngine

from .conftest import make_gazetteer
from .fakes import (ELIMINATION_ONLY_LINES, GOOD, NEEDS_LLM_LINES, UNCLAIMED_LINES, UNCLAIMED_STRUCTURED, make_pipeline, reply, submit, text)

ENGINE = RulesEngine(gazetteer=make_gazetteer())


# -- the scenarios of the diagnosis --------------------------------------------------------------------------------------------------
def test_a_model_that_drops_a_correct_elimination_field_ends_in_review():
    # "Zorb Hall" was set by the rules as a locality (by elimination, and correct); dropping it, and "Attn Accounts", loses text
    p = make_pipeline([submit(UNCLAIMED_STRUCTURED)] * 3)
    out = p.process("m1", UNCLAIMED_LINES)
    assert out.status == "review" and out.route == REVIEW and out.fields == {}
    assert "DROPS_TEXT" in out.reasons and "ATTEMPTS_EXHAUSTED" in out.reasons
    assert len(p.client.requests) == 3


def test_the_feedback_names_the_lost_text_and_does_not_invite_deleting_it():
    p = make_pipeline([submit(UNCLAIMED_STRUCTURED)] * 3)
    p.process("m1", UNCLAIMED_LINES)
    feedback = p.client.requests[1]["messages"][0]["content"]
    assert "DROPS_TEXT" in feedback and "Zorb Hall" in feedback and "Attn Accounts" in feedback
    assert "leave the offending parts out" not in feedback and "AdrLine" in feedback


def test_text_moved_to_adrline_gives_a_hybrid_that_routes_to_review():
    hybrid = {"TwnNm": "Cork", "Ctry": "IE", "AdrLine": ["Attn Accounts", "Zorb Hall 14 Main St T12 AC34"]}
    p = make_pipeline([submit(hybrid)])
    out = p.process("m1", UNCLAIMED_LINES)
    assert out.status == "review" and out.route == REVIEW and "HYBRID_FOR_REVIEW" in out.reasons and out.attempts == 1
    assert out.fields == {} and out.proposal == hybrid                      # the proposal is kept for the person, not published
    assert len(p.client.requests) == 1                                       # no point in retrying a valid hybrid


def test_a_model_that_overwrites_an_explicit_rules_field_is_rejected():
    overwritten = dict(GOOD, StrtNm="Railway Station")                       # real text from the landmark, in the street field
    p = make_pipeline([submit(overwritten)] * 3)
    out = p.process("m1", NEEDS_LLM_LINES)
    assert out.route == REVIEW and "CONTRADICTS_RULES:StrtNm" in out.reasons
    assert "CONTRADICTS_RULES:StrtNm" in p.client.requests[1]["messages"][0]["content"]


def test_every_explicit_rules_field_is_locked_not_just_a_few():
    for name, other in (("BldgNb", "10"), ("CtrySubDvsn", "Railway"), ("StrtNm", "Station")):
        p = make_pipeline([submit(dict(GOOD, **{name: other}))] * 3)
        assert f"CONTRADICTS_RULES:{name}" in p.process("m1", NEEDS_LLM_LINES).reasons, name


def test_a_legitimate_landmark_address_still_passes_completeness():
    p = make_pipeline([submit(GOOD)])
    out = p.process("m1", NEEDS_LLM_LINES)
    assert out.status == "repaired" and out.fields == GOOD and "DROPS_TEXT" not in out.reasons
    assert "opp. Railway Station" not in " ".join(out.fields.values())      # the landmark stays out of every field


def test_a_country_only_line_passes_completeness():
    rules = ENGINE.parse(["14 Main St", "Cork T12 AC34", "Ireland"])
    cand = Candidate(dict(rules.fields))
    from agent.repair import completeness
    assert completeness.check(cand, ["14 Main St", "Cork T12 AC34", "Ireland"], rules) == []
    assert completeness.check(Candidate(dict(rules.fields)), ["14 Main St", "Cork T12 AC34", "IE"], ENGINE.parse(["14 Main St", "Cork T12 AC34", "IE"])) == []
    p = make_pipeline([])
    assert p.process("m2", ["14 Main St", "Cork T12 AC34", "Ireland"]).status == "repaired"     # rules ACCEPT with country text


def test_the_model_is_skipped_when_only_unsupported_elimination_fields_stand_in_the_way():
    p = make_pipeline([])
    out = p.process("m1", ELIMINATION_ONLY_LINES)
    assert p.client.requests == [] and out.status == "review" and out.route == REVIEW
    assert "ELIMINATION_ONLY_NO_EVIDENCE" in out.reasons and out.cost_usd == 0 and out.attempts == 0
    assert out.proposal.get("TwnLctnNm") == "Zorb Hall"                      # the rules' guess goes to the person


def test_the_model_is_still_called_when_there_is_more_than_an_elimination_field():
    p = make_pipeline([submit(UNCLAIMED_STRUCTURED)])
    p.process("m1", UNCLAIMED_LINES)
    assert len(p.client.requests) >= 1                                      # unclaimed text as well: the model may help


def test_the_rules_accept_path_is_checked_for_completeness_too():
    class LossyEngine(RulesEngine):
        def parse(self, lines, hint=None):
            res = super().parse(lines, hint)
            res.fields.pop("StrtNm", None)                                  # a rules bug that loses text
            return res
    p = make_pipeline([], engine=LossyEngine(gazetteer=make_gazetteer()))
    out = p.process("m1", ["14 Main St", "Cork T12 AC34", "IE"])
    assert out.route == REVIEW and "DROPS_TEXT" in out.reasons


def test_the_validate_candidate_tool_gives_the_same_advice():
    from agent.repair.tools import AttemptContext
    ctx = AttemptContext(UNCLAIMED_LINES, None, ENGINE, rules=ENGINE.parse(UNCLAIMED_LINES))
    res = ctx.run("validate_candidate", {"address": UNCLAIMED_STRUCTURED})
    assert res["pass"] is False and "DROPS_TEXT" in res["reasons"]


# -- the completeness check itself ------------------------------------------------------------------------------------------------
def test_completeness_unit_cases():
    from agent.repair import completeness
    raw = ["14 Main St,", "Cork  T12 AC34", "IE"]
    full = Candidate({"BldgNb": "14", "StrtNm": "Main St", "TwnNm": "Cork", "PstCd": "T12 AC34", "Ctry": "IE"})
    assert completeness.check(full, raw) == []
    assert completeness.check(Candidate({"TwnNm": "Cork", "PstCd": "T12 AC34", "Ctry": "IE"}), raw) == ["14 Main St"]          # lost text is named
    assert completeness.check(Candidate({"BldgNb": "14", "StrtNm": "Main Street", "TwnNm": "Cork", "PstCd": "T12 AC34", "Ctry": "IE"}), raw) == []   # allowlisted expansion
    assert completeness.check(Candidate({"BldgNb": "14", "StrtNm": "Main St", "TwnNm": "Cork", "PstCd": "T12AC34", "Ctry": "IE"}), raw) == []         # postcode written without its space
    # hybrid: the text may sit in AdrLine
    assert completeness.check(Candidate({"TwnNm": "Cork", "Ctry": "IE"}, ["14 Main St", "T12 AC34"]), raw) == []
    # text counted once: a duplicate word cannot be dropped
    assert completeness.check(Candidate({"TwnNm": "Cork", "Ctry": "IE"}, ["Cork"]), ["Cork Cork", "IE"]) == []
    assert completeness.check(Candidate({"TwnNm": "Cork", "Ctry": "IE"}), ["Cork Cork", "IE"]) == ["Cork"]


def test_unit_prefix_pieces_are_accounted():
    from agent.repair import completeness
    cand = Candidate({"Room": "5", "BldgNb": "123", "StrtNm": "Kestrel Drive", "TwnNm": "Kingston", "Ctry": "CA"})
    assert completeness.check(cand, ["5-123 Kestrel Drive", "Kingston", "CA"]) == []


def test_country_text_is_exempt_only_for_the_candidates_country():
    from agent.repair import completeness
    ok = Candidate({"TwnNm": "Cork", "Ctry": "IE"})
    assert completeness.check(ok, ["Cork", "Ireland"]) == [] and completeness.check(ok, ["Cork", "IE"]) == []
    assert completeness.check(Candidate({"TwnNm": "Cork", "Ctry": "GB"}), ["Cork", "Ireland"]) == ["Ireland"]


def test_only_landmarks_the_rules_recognise_are_exempt():
    from agent.repair import completeness
    raw = NEEDS_LLM_LINES
    rules = ENGINE.parse(raw)
    cand = Candidate(dict(GOOD))
    assert completeness.check(cand, raw, rules) == []
    assert completeness.check(cand, raw, None) == ["opp. Railway Station"]            # without the rules' judgement it is lost text
    lines = ["Plot 5 Mill Road Pune Maharashtra 411001 {} the blue gate", "India"]
    cand = Candidate({"BldgNb": "Plot 5", "StrtNm": "Mill Road", "TwnNm": "Pune", "CtrySubDvsn": "Maharashtra", "PstCd": "411001", "Ctry": "IN"})
    known = [lines[0].format("behind"), lines[1]]          # "behind" is a landmark keyword of the IN profile: the rules recognise the phrase
    unknown = [lines[0].format("beyond"), lines[1]]         # "beyond" is not: the same text is lost text
    assert completeness.check(cand, known, ENGINE.parse(known)) == []
    assert completeness.check(cand, unknown, ENGINE.parse(unknown)) == ["beyond the blue gate"]


# -- property: any REPAIRED output accounts for every input token that is not exempt ---------------------------------------------------
SETTINGS = settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
BASES = [NEEDS_LLM_LINES, UNCLAIMED_LINES, ["14 Main St", "Cork T12 AC34", "IE"], ["Plot 5, Mill Road", "Pune, Maharashtra 411001", "India"]]
NOISE = ["Attn Accounts", "Zorb Hall", "Flat 2", "near the old gate", "c/o Mr Smith", "Ground Floor"]


@st.composite
def scenario(draw):
    raw = list(draw(st.sampled_from(BASES)))
    for extra in draw(st.lists(st.sampled_from(NOISE), max_size=2, unique=True)):
        raw.insert(draw(st.integers(0, len(raw))), extra)
    rules = ENGINE.parse(raw)
    base = dict(rules.fields) if rules.fields else {"Ctry": "IE", "TwnNm": "Cork"}
    answers = []
    for _ in range(draw(st.integers(1, 3))):
        addr = dict(base)
        for k in list(addr):
            if draw(st.integers(0, 4)) == 0:
                addr.pop(k)
        if draw(st.booleans()):
            addr["AdrLine"] = draw(st.lists(st.sampled_from(NOISE + ["14 Main St", "Plot 5", "Mill Road"]), max_size=2))
        answers.append(submit(addr))
    return raw, answers


def _words(s):
    return {w.strip(",.;()[]\"'").casefold() for w in s.replace("-", " ").replace("/", " ").split() if w.strip(",.;()[]\"'")}


@SETTINGS
@given(s=scenario())
def test_any_repaired_output_accounts_for_every_non_exempt_input_token(s):
    raw, answers = s
    pipe = make_pipeline(answers, default=reply(text("done"), stop="end_turn"))
    out = pipe.process("p1", raw)
    assert not any(r.startswith("INTERNAL_ERROR") for r in out.reasons)
    if out.status != "repaired":
        return
    rules = ENGINE.parse(raw)
    exempt = set()
    for l in rules.leftovers:
        if l.reason.startswith("landmark"):
            exempt |= _words(l.text)
    ctry = out.fields.get("Ctry", "")
    prof = ENGINE.profiles.get(ctry)
    if prof:
        exempt |= {ctry.casefold()} | {w for n in prof.names for w in _words(n)}
    produced = set()
    for v in list(out.fields.values()) + out.adr_lines:
        produced |= _words(v)
    from agent.rules import allowlist
    produced_c = {allowlist.canonical(w, ctry) for w in produced}
    for w in _words(" ".join(raw)):
        assert w in exempt or w in produced or allowlist.canonical(w, ctry) in produced_c, (w, raw, out.fields)
