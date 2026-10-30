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


class Agent(System):
    """The repair pipeline of agent.repair: rules first, the model only for NEEDS_LLM, plain code decides every route.

    REPAIRED is reported as ACCEPT (it is an automatic repair); REVIEW (including retry_later) as REVIEW. The model never has the final say.
    Results are kept in memory (no database); the cost is the API's token usage times agent/config/prices.yml.
    """
    name = "agent"

    def __init__(self, client=None, use_gazetteer: bool = True, engine=None):
        import os
        from agent.repair.config import model_from_env
        self.client = client
        self.use_gazetteer = use_gazetteer
        self.engine = engine
        self.model = model_from_env()
        self._have_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
        self._pipeline = None
        self._n = 0
        self.total_cost = 0.0

    @property
    def available(self) -> bool:
        return self.client is not None or self._have_key

    @property
    def unavailable_reason(self) -> str:
        return "not available: ANTHROPIC_API_KEY is not set in the environment (the key is read from the environment only)"

    def _build(self):
        from agent.repair.config import load_routing
        from agent.repair.store import InMemoryRepository
        from agent.repair.worker import build_pipeline
        from agent.rules.engine import RulesEngine
        from agent.rules.gazetteer import Gazetteer
        routing = load_routing()
        engine = self.engine or (RulesEngine() if self.use_gazetteer else RulesEngine(gazetteer=Gazetteer()))
        self._routing = routing
        return build_pipeline(InMemoryRepository(routing["max_payment_tries"], routing["lease_seconds"]), client=self.client, routing=routing, engine=engine)

    def config(self) -> dict:
        from agent.repair.config import Prices
        from agent.repair.prompts import PROMPT_VERSION
        from agent.rules.engine import load_config
        r = self._routing if self._pipeline else __import__("agent.repair.config", fromlist=["load_routing"]).load_routing()
        return {"model": self.model, "prompt_version": PROMPT_VERSION, "thresholds": {"repaired": r["threshold"], "rules_accept": load_config()["thresholds"]["accept"]},
                "max_attempts": r["max_attempts"], "max_tool_calls": r["max_tool_calls"], "max_cost_usd_per_payment": r["max_cost_usd_per_payment"],
                "effort": r["effort"], "temperature": "not sent (claude-haiku-5-5 rejects non-default sampling parameters)",
                "prices_checked": Prices.load().checked, "gazetteer": "cities500" if self.use_gazetteer else "none"}

    def run(self, raw_lines, country_hint=None) -> SystemOutput:
        if not self.available:
            raise NotAvailable(f"agent: {self.unavailable_reason}")
        if self._pipeline is None:
            self._pipeline = self._build()
        self._n += 1
        t0 = time.perf_counter()
        out = self._pipeline.process(f"eval-{self._n}", raw_lines, country_hint)
        latency = time.perf_counter() - t0
        self.total_cost += out.cost_usd
        route = "ACCEPT" if out.status == "repaired" else "REVIEW"
        return SystemOutput(dict(out.fields), route, latency, out.cost_usd,
                            {"status": out.status, "source": out.source, "attempts": out.attempts, "reasons": list(out.reasons), "adr_lines": list(out.adr_lines)})


SYSTEMS = {"rules_only": RulesOnly, "llm_only": LlmOnly, "agent": Agent}
