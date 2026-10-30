"""A scripted fake LLM client: no key, no network. Each scripted item is a response, an exception to raise, or a callable(kwargs)."""
from __future__ import annotations

import itertools
from types import SimpleNamespace

from agent.repair.agent import RepairAgent
from agent.repair.config import Prices, load_routing
from agent.repair.pipeline import RepairPipeline
from agent.repair.store import InMemoryRepository
from agent.rules.engine import RulesEngine

from .conftest import make_gazetteer

_ids = itertools.count(1)


def text(t: str):
    return SimpleNamespace(type="text", text=t)


def call(name: str, args, id: str | None = None):
    return SimpleNamespace(type="tool_use", id=id or f"toolu_{next(_ids)}", name=name, input=args)


def reply(*blocks, tin: int = 1000, tout: int = 100, stop: str = "tool_use"):
    return SimpleNamespace(content=list(blocks), stop_reason=stop, usage=SimpleNamespace(input_tokens=tin, output_tokens=tout))


def submit(address: dict, confidence: float = 0.95, rationale: str = "copied from the lines", rules=("normalise",), **kw):
    return reply(call("submit_repair", {"address": address, "confidence": confidence, "rationale": rationale, "evidence_rules": list(rules)}), **kw)


class ScriptedClient:
    def __init__(self, script, default=None):
        self.script = list(script)
        self.default = default
        self.requests: list[dict] = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        if not self.script and self.default is not None:
            return self.default
        if not self.script:
            raise AssertionError("the script ran out: the agent made one call too many")
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item(kwargs) if callable(item) else item


TEST_THRESHOLD = 0.85     # tests that are not about the applied threshold use this one, so a recalibration cannot change what they test


def explicit_routing(**overrides) -> dict:
    """routing.yml with an explicit test threshold. The confidence constants are the real (frozen) ones; the threshold is not read from the file."""
    routing = load_routing()
    routing["threshold"] = TEST_THRESHOLD
    routing.update(overrides)
    return routing


def make_pipeline(script, gazetteer=None, routing_overrides=None, repo=None, engine=None, default=None, routing=None):
    """`routing` is an explicit configuration; by default explicit_routing() (threshold 0.85). Pass load_routing() only to test the applied threshold."""
    routing = dict(routing) if routing is not None else explicit_routing()
    routing.update(routing_overrides or {})
    engine = engine or RulesEngine(gazetteer=gazetteer if gazetteer is not None else make_gazetteer())
    client = ScriptedClient(script, default)
    sleeps: list[float] = []
    agent = RepairAgent(client, engine, "claude-haiku-5-5", routing, Prices.load(), sleep=sleeps.append)
    repo = repo if repo is not None else InMemoryRepository(max_payment_tries=routing["max_payment_tries"])
    pipe = RepairPipeline(engine, agent, repo, routing)
    pipe.client, pipe.sleeps = client, sleeps
    return pipe


# An address the rules send to the model although every field has explicit evidence: the landmark ran into the town, so where it
# stops is a guess (landmark_unbounded). The model can only confirm the rules' fields; the landmark text is exempt from completeness.
NEEDS_LLM_LINES = ["No. 10 Hospital Marg opp. Railway Station Jaipur Rajasthan 302006", "India"]
GOOD = {"BldgNb": "No. 10", "StrtNm": "Hospital Marg", "TwnNm": "Jaipur", "CtrySubDvsn": "Rajasthan", "PstCd": "302006", "Ctry": "IN"}

# Unclaimed text ("Attn Accounts") plus a locality found by elimination ("Zorb Hall"): the model is called, and can place neither
# with support, so it cannot produce a repair without losing text.
UNCLAIMED_LINES = ["Attn Accounts", "Zorb Hall", "14 Main St", "Cork T12 AC34", "IE"]
UNCLAIMED_STRUCTURED = {"BldgNb": "14", "StrtNm": "Main St", "TwnNm": "Cork", "PstCd": "T12 AC34", "Ctry": "IE"}
# Only an elimination field stands between this and ACCEPT: the model is skipped.
ELIMINATION_ONLY_LINES = ["14 Main St", "Zorb Hall", "Cork T12 AC34", "IE"]
