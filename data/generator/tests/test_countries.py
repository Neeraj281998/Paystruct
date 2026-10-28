from __future__ import annotations

import random

import pytest

from addrgen import countries
from addrgen.countries import ie
from addrgen.countries.base import _REGISTRY, TEMPLATES_BY_DIFFICULTY, _TEMPLATES, CountryModule, register
from addrgen.generate import generate_record
from addrgen.model import Part, TownBlock
from addrgen.validate import check_record


def test_ie_and_gb_are_registered():
    assert countries.codes() == ["GB", "IE"]
    assert countries.get("ie").code == "IE"
    with pytest.raises(KeyError, match="No country module"):
        countries.get("ZZ")


@pytest.mark.parametrize("code", ["IE", "GB"])
def test_a_module_provides_everything_the_framework_needs(code):
    m = countries.get(code)
    assert len(m.code) == 2 and m.locale and m.country_names
    assert set(m.template_weights) <= set(_TEMPLATES)
    for tier, templates in TEMPLATES_BY_DIFFICULTY.items():
        assert any(t in m.template_weights for t in templates), tier
    assert m.split_postcode("AB1 2CD") == ("AB1", "2CD")
    assert m.split_postcode("AB12CD") is None


def test_dublin_districts_follow_the_real_numbering():
    names = {d for d, _ in ie.DUBLIN_DISTRICTS}
    assert {"Dublin 1", "Dublin 6W", "Dublin 24"} <= names
    assert not names & {"Dublin 19", "Dublin 21", "Dublin 23"}
    assert dict(ie.DUBLIN_DISTRICTS)["Dublin 6W"] == "D6W"


def test_postal_districts_only_appear_in_hard_records():
    module, rng = countries.get("IE"), random.Random(1)
    for tier in ("easy", "medium"):
        for _ in range(300):
            assert "postal_district" not in module.make_truth(rng, tier).tags


def test_eircodes_use_only_the_characters_eircode_allows():
    module, rng = countries.get("IE"), random.Random(2)
    for _ in range(300):
        truth = module.make_truth(rng, "hard")
        pc = next(p.text for seg in truth.segments for p in seg if p.field == "PstCd")
        assert len(pc) == 8 and set(pc.split(" ")[1]) <= set(ie._EIRCODE_CHARS)


def test_adding_a_country_is_adding_one_small_module():
    """A new country needs only this: data, a town block and a postcode split. The generator, corruptions, tags,
    difficulty and validation all work unchanged."""

    @register
    class Testland(CountryModule):
        code = "XX"
        locale = "en_GB"
        country_names = ("Testland",)
        street_bases = ("Main", "Mill")
        street_suffixes = (("Street", 1.0),)
        building_bases = ("Elm",)
        building_words = (("House", 1.0),)
        place_names = ("Harbour",)
        template_weights = {"number_street": 1.0, "po_box": 1.0}

        def town_block(self, rng, difficulty, want_locality):
            return TownBlock([[Part("TwnNm", "Testville"), Part("PstCd", "AA1 1AA")]], set())

        def split_postcode(self, postcode):
            return tuple(postcode.split(" "))

    try:
        assert "XX" in countries.codes()
        for tier in ("easy", "medium", "hard"):
            rec = generate_record(1, "XX", 0, tier)
            assert rec["country"] == "XX" and rec["gold"]["Ctry"] == "XX" and check_record(rec) == []
    finally:
        _REGISTRY.pop("XX")
    assert countries.codes() == ["GB", "IE"]
