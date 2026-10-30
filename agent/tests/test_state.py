from agent.rules.state import ParseState, SEP_COMMA, SEP_COMMA_LINE, SEP_LINE, SEP_NONE, tokenize


def toks(lines, wrap=70):
    text, tokens = tokenize(lines, wrap)
    return text, tokens


def test_spans_are_offsets_into_the_joined_text():
    text, tokens = toks(["14 Main St,", "  Cork  T12 AB34"])
    for t in tokens:
        assert text[t.start:t.end] == t.text
    assert [t.text for t in tokens] == ["14", "Main", "St", "Cork", "T12", "AB34"]


def test_commas_dashes_slashes_and_brackets_become_separators_not_tokens():
    _, tokens = toks(["Sherbrooke (Québec) - J1H 5K9 / Canada"])
    assert [t.text for t in tokens] == ["Sherbrooke", "Québec", "J1H", "5K9", "Canada"]
    assert [t.sep for t in tokens] == [SEP_COMMA, SEP_COMMA, SEP_NONE, SEP_COMMA, SEP_LINE]


def test_separator_strength():
    _, tokens = toks(["a b,", "c", "d,"])
    assert [t.sep for t in tokens] == [SEP_NONE, SEP_COMMA_LINE, SEP_LINE, SEP_COMMA_LINE]


def test_a_line_wrapped_at_the_limit_continues():
    long_line = "x" * 60 + " opp. Railway"
    _, tokens = toks([long_line, "Station, Sector 41"], wrap=len(long_line) + 3)
    railway = next(t for t in tokens if t.text == "Railway")
    assert railway.sep == SEP_NONE  # "Station" would not have fitted, so the break is a wrap
    _, tokens = toks(["short line", "Station"])
    assert tokens[1].sep == SEP_LINE


def test_text_is_nfc_and_original_case_is_kept():
    text, tokens = toks(["Café STRASSE"])
    assert text == "Café STRASSE" and tokens[0].text == "Café" and tokens[1].text == "STRASSE"


def test_empty_and_punctuation_only_input():
    assert toks([])[1] == [] and toks(["", "  ", ",,,", "- / -"])[1] == []


def test_claim_sets_field_spans_and_roles():
    s = ParseState(raw_lines=["12 Main St"])
    s.text, s.tokens = tokenize(s.raw_lines)
    s.claim("StrtNm", [1, 2], "t", "why", 0.9)
    assert s.fields["StrtNm"] == "Main St" and s.spans["StrtNm"] == [(3, 10)] and s.roles[1] == "StrtNm"
    assert s.free_indexes() == [0]


def test_copy_does_not_share_state():
    s = ParseState(raw_lines=["12 Main St"])
    s.text, s.tokens = tokenize(s.raw_lines)
    c = s.copy()
    c.claim("BldgNb", [0], "t", "why", 0.9)
    assert "BldgNb" not in s.fields and s.is_free(0)
