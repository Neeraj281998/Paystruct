"""Property tests: for random raw lines and random scripted model outputs, a REPAIRED output is always grounded, within the
XSD limits, and the code never raises (an internal error would show up as an INTERNAL_ERROR reason)."""
from hypothesis import HealthCheck, given, settings, strategies as st

from agent.repair import grounding
from agent.repair.agent import TransientApiError
from agent.repair.iso3166 import ALPHA2
from agent.repair.pipeline import REPAIRED
from agent.repair.store import InMemoryRepository
from agent.repair.validator import max_adr_lines
from agent.rules.xsd import V1_FIELDS, load_schema
from evals.metrics import hallucinated_fields

from .fakes import call, make_pipeline, reply, submit, text
from .test_properties import hints, lines_random, lines_words

SCHEMA = load_schema()
SETTINGS = settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])

WORDS = ["Cork", "Main", "St", "14", "T12", "AC34", "IE", "GB", "Dublin", "Street", "Co.", "Kerry", "Flat", "2", "Paris", "75008", "Rue", "Attn", "Zorb"]


@st.composite
def model_address(draw, raw_lines):
    pool = [w for l in raw_lines for w in l.replace(",", " ").split()] or ["x"]
    value = st.one_of(st.sampled_from(pool), st.sampled_from(WORDS), st.text(min_size=1, max_size=30),
                      st.lists(st.sampled_from(pool), min_size=1, max_size=4).map(" ".join), st.text(min_size=1, max_size=300))
    addr = {f: draw(value) for f in draw(st.lists(st.sampled_from(V1_FIELDS), unique=True, max_size=8))}
    if draw(st.booleans()):
        addr["Ctry"] = draw(st.sampled_from(sorted(ALPHA2)[:30] + ["IE", "GB", "FR", "ZZ"]))
    if draw(st.booleans()):
        addr["AdrLine"] = draw(st.lists(value, max_size=4))
    return addr


@st.composite
def scenario(draw):
    raw = draw(st.one_of(lines_words, lines_random))
    actions = []
    for _ in range(draw(st.integers(0, 6))):
        kind = draw(st.sampled_from(["submit", "submit", "parse", "garbage", "text", "outage", "country"]))
        if kind == "submit":
            actions.append(submit(draw(model_address(raw)), confidence=draw(st.floats(0, 1)), rules=tuple(draw(st.lists(st.sampled_from(["normalise", "country", "postcode", "made_up"]), min_size=1, max_size=3)))))
        elif kind == "parse":
            actions.append(reply(call("parse_address", {"lines": raw or ["x"]})))
        elif kind == "garbage":
            actions.append(reply(call(draw(st.sampled_from(["approve", "parse_address", "submit_repair"])), draw(st.one_of(st.none(), st.text(max_size=10), st.dictionaries(st.text(max_size=5), st.integers(), max_size=3))))))
        elif kind == "text":
            actions.append(reply(text("ok"), stop="end_turn"))
        elif kind == "country":
            actions.append(reply(call("country_lookup", {"text": draw(st.text(min_size=1, max_size=20))})))
        else:
            actions.append(TransientApiError())
    return raw, draw(hints), actions


def check_outcome(pipe, out, raw):
    assert not any(r.startswith("INTERNAL_ERROR") for r in out.reasons), out.reasons
    assert out.status in ("repaired", "review", "retry_later")
    assert out.attempts <= 3 and out.cost_usd >= 0
    if out.status == "repaired":
        assert out.route == REPAIRED and out.confidence >= pipe.cfg["threshold"]
        assert hallucinated_fields(out.fields, raw, out.fields.get("Ctry", "")) == []
        for name, value in out.fields.items():
            limit = SCHEMA.max_length(name)
            assert limit is None or len(value) <= limit
        if "Ctry" in out.fields:
            assert out.fields["Ctry"] in ALPHA2
        assert "TwnNm" in out.fields and "Ctry" in out.fields
        assert len(out.adr_lines) <= max_adr_lines() and all(len(l) <= 70 for l in out.adr_lines)
        for line in out.adr_lines:
            assert grounding.words_grounded(line, raw, out.fields.get("Ctry", ""))
    else:
        assert out.fields == {}


@SETTINGS
@given(s=scenario())
def test_every_repaired_output_is_grounded_within_limits_and_the_code_never_raises(s):
    raw, hint, actions = s
    pipe = make_pipeline(actions, default=reply(text("done"), stop="end_turn"), repo=InMemoryRepository())
    check_outcome(pipe, pipe.process("p1", raw, hint), raw)


# Realistic addresses (so that many reach the model and some are repaired) and a model that mutates a good answer at random.
BLOCKS = ["Attn Accounts", "14 Main St", "Cork T12 AC34", "IE", "Flat 2", "Templeogue", "Mulberry Hall", "Dublin 16", "D16 X0F3", "PO Box 12",
          "Ground Floor", "Zorbleville", "Co. Cork", "Ireland", "Rathmines Road Lower", "Block C Fenmore Business Park", "12 Elm Way", "Bristol BS6 7QD"]
GOODS = [{"BldgNb": "14", "StrtNm": "Main St", "TwnNm": "Cork", "PstCd": "T12 AC34", "Ctry": "IE"}, {"TwnNm": "Cork", "Ctry": "IE", "AdrLine": ["Attn Accounts", "14 Main St"]},
         {"Room": "Flat 2", "StrtNm": "Main St", "TwnNm": "Cork", "Ctry": "IE"}, {"TwnNm": "Dublin 16", "PstCd": "D16 X0F3", "Ctry": "IE", "BldgNm": "Mulberry Hall"},
         {"StrtNm": "Elm Way", "BldgNb": "12", "TwnNm": "Bristol", "PstCd": "BS6 7QD", "Ctry": "GB"}]


IN_LINES = ["No. 10 Hospital Marg opp. Railway Station Jaipur Rajasthan 302006", "India"]
GOODS_IN = [{"BldgNb": "No. 10", "StrtNm": "Hospital Marg", "TwnNm": "Jaipur", "CtrySubDvsn": "Rajasthan", "PstCd": "302006", "Ctry": "IN"},
            {"TwnNm": "Jaipur", "Ctry": "IN", "AdrLine": ["No. 10 Hospital Marg", "Rajasthan 302006"]}]


@st.composite
def realistic(draw):
    if draw(st.integers(0, 2)) == 0:
        raw = list(IN_LINES)
        answers = []
        for _ in range(draw(st.integers(1, 3))):
            addr = dict(draw(st.sampled_from(GOODS_IN)))
            for k in (list(addr) if draw(st.booleans()) else []):
                how = draw(st.sampled_from(["keep", "invent", "drop", "long"]))
                if how == "drop":
                    addr.pop(k)
                elif how == "invent" and k != "AdrLine":
                    addr[k] = draw(st.sampled_from(["Mumbai", "99", "ZZ", "Nowhere Road"]))
                elif how == "long" and k != "AdrLine":
                    addr[k] = addr[k] * 40
            answers.append(submit(addr, confidence=draw(st.floats(0, 1)), rules=("normalise",)))
        return raw, "IN", answers
    if draw(st.booleans()):
        noise = draw(st.lists(st.sampled_from(["Attn Accounts", "Mulberry Hall", "Zorbleville", "Flat 2", "Ground Floor", "PO Box 12", "Templeogue"]), max_size=2, unique=True))
        raw = draw(st.permutations(["14 Main St", "Cork T12 AC34", "IE", *noise]))
    else:
        raw = draw(st.lists(st.sampled_from(BLOCKS), min_size=1, max_size=6))
    answers = []
    for _ in range(draw(st.integers(1, 3))):
        addr = dict(draw(st.sampled_from(GOODS)))
        for k in (list(addr) if draw(st.booleans()) else []):
            how = draw(st.sampled_from(["keep", "keep", "keep", "invent", "drop", "long"]))
            if how == "drop":
                addr.pop(k)
            elif how == "invent" and k != "AdrLine":
                addr[k] = draw(st.sampled_from(["Galway", "99", "ZZ", "Nowhere Road", "A1 B2C"]))
            elif how == "long" and k != "AdrLine":
                addr[k] = addr[k] * 40
        answers.append(submit(addr, confidence=draw(st.floats(0, 1)), rules=("normalise",)))
    return raw, draw(st.sampled_from([None, "IE", "GB"])), answers


@SETTINGS
@given(s=realistic())
def test_realistic_addresses_with_mutated_model_answers(s):
    raw, hint, answers = s
    pipe = make_pipeline(answers, default=reply(text("done"), stop="end_turn"), repo=InMemoryRepository())
    check_outcome(pipe, pipe.process("p1", raw, hint), raw)


def test_the_realistic_generator_does_reach_repaired_outputs():
    """Guards the property test against being vacuous: a good answer to a NEEDS_LLM address is repaired."""
    pipe = make_pipeline([submit(GOODS_IN[0], rules=("normalise",))])
    out = pipe.process("p1", IN_LINES)
    assert out.status == "repaired"


@SETTINGS
@given(raw=st.one_of(lines_words, lines_random), hint=hints)
def test_no_model_call_is_made_unless_the_rules_say_needs_llm(raw, hint):
    pipe = make_pipeline([], default=reply(text("done"), stop="end_turn"))
    out = pipe.process("p2", raw, hint)
    if out.rules_route in ("ACCEPT", "REVIEW"):
        assert pipe.client.requests == []
