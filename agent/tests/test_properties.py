"""Hypothesis property tests: the engine never raises, never exceeds an XSD length, never invents a value."""
import string

from hypothesis import HealthCheck, given, settings, strategies as st

from agent.rules.engine import RulesEngine
from agent.rules.xsd import V1_FIELDS, load_schema

from .conftest import make_gazetteer

ENGINE = RulesEngine(gazetteer=make_gazetteer())
SCHEMA = load_schema()

ALPHABET = string.ascii_letters + string.digits + " ,.;-/()#'\"" + "éèüöäßñ́​\t"
WORDS = ["Cork", "Dublin", "Rue", "Street", "St", "Flat", "Unit", "12", "T12", "AC34", "BS6", "7QD", "Floor", "PO", "Box", "Co.", "Galway",
         "France", "IE", "GB", "CA", "US", "IN", "Plot", "No.", "near", "Paris", "75008", "Straße", "Weg", "NL", "1015", "CJ", "Delhi", "110092"]

lines_random = st.lists(st.text(alphabet=ALPHABET, max_size=120), max_size=8)
lines_words = st.lists(st.lists(st.sampled_from(WORDS) | st.text(alphabet=ALPHABET, max_size=12), max_size=14).map(" ".join), max_size=7)
hints = st.sampled_from([None, "IE", "GB", "FR", "DE", "NL", "CA", "US", "IN", "XX"])

SETTINGS = settings(max_examples=250, deadline=None, suppress_health_check=[HealthCheck.too_slow])


@SETTINGS
@given(lines=st.one_of(lines_random, lines_words), hint=hints)
def test_the_engine_never_raises(lines, hint):
    ENGINE.parse(lines, hint)


@SETTINGS
@given(lines=st.one_of(lines_random, lines_words), hint=hints)
def test_no_output_field_exceeds_its_xsd_maximum(lines, hint):
    r = ENGINE.parse(lines, hint)
    for name, value in r.fields.items():
        assert name in V1_FIELDS and value
        limit = SCHEMA.max_length(name)
        assert limit is None or len(value) <= limit, (name, value)
    if "Ctry" in r.fields:
        assert len(r.fields["Ctry"]) == 2 and r.fields["Ctry"].isupper()
    if r.hybrid:
        assert len(r.hybrid["AdrLine"]) <= ENGINE.config["max_adr_lines"] <= SCHEMA.max_occurs("AdrLine")
        assert all(len(l) <= SCHEMA.max_length("AdrLine") for l in r.hybrid["AdrLine"])


@SETTINGS
@given(lines=st.one_of(lines_random, lines_words), hint=hints)
def test_every_value_but_the_country_is_built_from_tokens_in_the_input(lines, hint):
    r = ENGINE.parse(lines, hint)
    for name, value in r.fields.items():
        if name == "Ctry":
            continue
        for word in value.split(" "):
            assert word in r.text, (name, value)
        assert name in r.spans and r.spans[name]
        span_words = " ".join(r.text[s:e] for s, e in r.spans[name]).split()
        assert set(value.split(" ")) <= set(span_words) | {w for w in value.split(" ") if w in r.text}


@SETTINGS
@given(lines=st.one_of(lines_random, lines_words))
def test_no_town_is_ever_derived_without_a_postcode_or_town_text(lines):
    """With no TwnNm in the output, the route is never ACCEPT."""
    r = ENGINE.parse(lines)
    if "TwnNm" not in r.fields:
        assert r.route == "REVIEW"


@SETTINGS
@given(lines=st.one_of(lines_random, lines_words), hint=hints)
def test_leftover_and_span_offsets_are_inside_the_text(lines, hint):
    r = ENGINE.parse(lines, hint)
    for l in r.leftovers:
        assert 0 <= l.start < l.end <= len(r.text) and r.text[l.start:l.end] == l.text
    for spans in r.spans.values():
        for s, e in spans:
            assert 0 <= s <= e <= len(r.text)


@SETTINGS
@given(lines=lines_words, hint=hints)
def test_the_engine_is_deterministic(lines, hint):
    assert ENGINE.parse(lines, hint).as_dict() == ENGINE.parse(lines, hint).as_dict()
