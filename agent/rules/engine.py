"""The rules engine: a configurable chain of small rules over a ParseState."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from agent.rules import gazetteer as gaz_mod
from agent.rules.base import Rule, RuleContext
from agent.rules.profile import Profile, all_profiles
from agent.rules.rule_country import CountryRule
from agent.rules.rule_finalize import ConfidenceRule, HybridRule, LengthRule, RoutingRule
from agent.rules.rule_landmark import LandmarkRule
from agent.rules.rule_locality import LocalityPatternRule, LocalityRule
from agent.rules.rule_normalise import NormaliseRule
from agent.rules.rule_postcode import PostcodeRule
from agent.rules.rule_region import RegionRule
from agent.rules.rule_street import StreetRule
from agent.rules.rule_town import TownRule
from agent.rules.rule_units import FloorRule, PoBoxRule, UnitRule
from agent.rules.state import Leftover, ParseState
from agent.rules.xsd import load_schema

CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"

REGISTRY: dict[str, type[Rule]] = {r.id: r for r in (
    NormaliseRule, CountryRule, PostcodeRule, RegionRule, LandmarkRule, PoBoxRule, FloorRule, UnitRule, TownRule,
    StreetRule, LocalityRule, LocalityPatternRule, LengthRule, ConfidenceRule, RoutingRule, HybridRule)}


def load_config(path: Path = CONFIG_PATH) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@dataclass
class RulesResult:
    fields: dict[str, str]
    route: str
    confidence: float
    field_confidence: dict[str, float]
    field_basis: dict[str, str]
    evidence: dict[str, list[tuple[str, str]]]
    spans: dict[str, list[tuple[int, int]]]
    leftovers: list[Leftover]
    flags: list[str]
    route_reasons: list[str]
    hybrid: dict | None
    country: str | None
    text: str

    def as_dict(self) -> dict:
        return {"fields": self.fields, "route": self.route, "confidence": self.confidence,
                "leftovers": [l.__dict__ for l in self.leftovers], "flags": self.flags, "hybrid": self.hybrid}


class RulesEngine:
    def __init__(self, config: dict | None = None, profiles: dict[str, Profile] | None = None, gazetteer=None, order: list[str] | None = None):
        self.config = config or load_config()
        self.profiles = profiles or all_profiles()
        self.gazetteer = gazetteer if gazetteer is not None else gaz_mod.default_gazetteer()
        self.schema = load_schema()
        self.ctx = RuleContext(self.profiles, self.gazetteer, self.schema, self.config)
        self.order = order or list(self.config["order"])
        self.rules = [REGISTRY[r](self.ctx) for r in self.order]

    def run(self, state: ParseState) -> ParseState:
        for rule in self.rules:
            state = rule.apply(state)
        return state

    def parse(self, raw_lines: list[str], country_hint: str | None = None) -> RulesResult:
        state = self.run(ParseState(raw_lines=list(raw_lines), country_hint=country_hint))
        return RulesResult(
            fields=dict(state.fields), route=state.route or "REVIEW", confidence=state.address_confidence or 0.0,
            field_confidence=dict(state.confidence), field_basis=dict(state.basis), evidence={k: [(e.rule, e.why) for e in v] for k, v in state.evidence.items()},
            spans={k: list(v) for k, v in state.spans.items()}, leftovers=list(state.leftovers), flags=list(state.flags),
            route_reasons=list(state.notes.get("route_reasons", [])), hybrid=state.hybrid, country=state.country, text=state.text)


@lru_cache(maxsize=1)
def default_engine() -> RulesEngine:
    return RulesEngine()
