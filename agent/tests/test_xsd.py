from agent.rules.xsd import V1_FIELDS, XSD_PATH, load_schema

PAIN = XSD_PATH.with_name("pain.001.001.13.xsd")


def test_lengths_come_from_the_xsd():
    s = load_schema()
    assert s.max_length("StrtNm") == 140 and s.max_length("BldgNm") == 140 and s.max_length("TwnNm") == 140
    assert s.max_length("BldgNb") == 16 and s.max_length("PstBx") == 16 and s.max_length("PstCd") == 16
    assert s.max_length("Flr") == 70 and s.max_length("Room") == 70 and s.max_length("CtrySubDvsn") == 35
    assert s.max_length("TwnLctnNm") == 140


def test_country_code_pattern_and_adrline_count():
    s = load_schema()
    assert s.elements["Ctry"].pattern == "[A-Z]{2,2}"
    assert s.max_occurs("AdrLine") == 7 and s.max_length("AdrLine") == 70


def test_every_v1_field_exists_in_the_schema():
    assert set(V1_FIELDS) <= set(load_schema().order())


def test_both_message_types_define_the_same_address():
    a, b = load_schema(XSD_PATH), load_schema(PAIN)
    assert {k: (v.max_length, v.max_occurs, v.pattern) for k, v in a.elements.items()} == \
           {k: (v.max_length, v.max_occurs, v.pattern) for k, v in b.elements.items()}
