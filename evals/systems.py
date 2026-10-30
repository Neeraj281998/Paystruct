"""The common interface: a system takes raw_lines and an optional country_hint and returns fields, a route, latency, cost."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


class NotAvailable(Exception):
    """A system that has not been built yet."""


@dataclass
class SystemOutput:
    fields: dict[str, str]
    route: str  # ACCEPT, NEEDS_LLM or REVIEW
    latency_s: float
    cost_usd: float = 0.0
    extra: dict = field(default_factory=dict)


class System:
    name = "system"
    available = True
    unavailable_reason = ""

    def config(self) -> dict:
        return {}

    def run(self, raw_lines: list[str], country_hint: str | None = None) -> SystemOutput:  # pragma: no cover - interface
        raise NotImplementedError


class RulesOnly(System):
    """The Python rules engine alone (agent.rules). Every non-ACCEPT record counts as not repaired."""
    name = "rules_only"

    def __init__(self, engine=None, use_gazetteer: bool = True):
        from agent.rules.engine import RulesEngine, load_config
        from agent.rules.gazetteer import Gazetteer
        self.use_gazetteer = use_gazetteer
        self.engine = engine or (RulesEngine() if use_gazetteer else RulesEngine(gazetteer=Gazetteer()))
        self._config = load_config()

    def config(self) -> dict:
        c = self._config
        return {"model": None, "prompt_version": None, "thresholds": c["thresholds"], "order": c["order"],
                "elimination_cap": c["signals"]["elimination_cap"], "max_adr_lines": c["max_adr_lines"],
                "gazetteer": "cities500" if self.use_gazetteer else "none"}

    def run(self, raw_lines, country_hint=None) -> SystemOutput:
        t0 = time.perf_counter()
        res = self.engine.parse(raw_lines, country_hint)
        return SystemOutput(dict(res.fields), res.route, time.perf_counter() - t0, 0.0,
                            {"route_reasons": list(res.route_reasons)})


class _NotYet(System):
    available = False

    def run(self, raw_lines, country_hint=None):
        raise NotAvailable(f"{self.name}: {self.unavailable_reason}")


class LlmOnly(_NotYet):
    name = "llm_only"
    unavailable_reason = "not yet available (built on Day 5: an LLM with no verification)"


class Agent(_NotYet):
    name = "agent"
    unavailable_reason = "not yet available (built on Days 4 and 5: the repair agent with the verifier)"


SYSTEMS = {"rules_only": RulesOnly, "llm_only": LlmOnly, "agent": Agent}
