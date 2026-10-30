"""Propose, then verify. The rules run first; the model is called only for NEEDS_LLM; plain code decides every route.

  rules ACCEPT      no model call; the output still goes through the validator and the grounding check (failure -> REVIEW)
  rules REVIEW      missing town, contradiction: not sent to the model
  rules NEEDS_LLM   the agent proposes (up to 3 attempts); a proposal is accepted only if the validator AND the grounding
                    check pass and every field has support; otherwise the reasons go back to the agent, then REVIEW
  routing           valid + grounded + confidence >= threshold -> REPAIRED; everything else -> REVIEW
"""
from __future__ import annotations

from dataclasses import dataclass, field

from agent.repair import grounding, support
from agent.repair.agent import AttemptResult, RepairAgent, Step
from agent.repair.store import Claim
from agent.repair.validator import Candidate, validate
from agent.rules.engine import RulesEngine
from agent.rules.profile import all_profiles
from agent.rules.scoring import values_equal

REPAIRED, REVIEW = "REPAIRED", "REVIEW"


@dataclass
class Outcome:
    msg_id: str
    status: str                       # repaired | review | retry_later | skipped
    route: str | None = None          # REPAIRED | REVIEW
    fields: dict = field(default_factory=dict)
    adr_lines: list[str] = field(default_factory=list)
    confidence: float | None = None
    attempts: int = 0
    cost_usd: float = 0.0
    reasons: list[str] = field(default_factory=list)
    source: str = "none"              # rules | agent | rules_review | none
    steps: list[Step] = field(default_factory=list)
    rules_route: str | None = None

    def address(self) -> dict:
        out = dict(self.fields)
        if self.adr_lines:
            out["AdrLine"] = list(self.adr_lines)
        return out


def compute_confidence(fields: dict, rules, attempt: int, model_conf: float | None, unsupported: list[str], unchecked: bool, routing: dict) -> float:
    """Confidence from signals computed in code. The model's own number is one weak signal, centred on 0.5."""
    c = routing["confidence"]
    non_ctry = {k: v for k, v in fields.items() if k != "Ctry"}
    agree = sum(1 for k, v in non_ctry.items()
                if rules.field_basis.get(k) == "explicit" and k in rules.fields and values_equal(v, rules.fields[k], k, fields.get("Ctry", "")))
    share = agree / len(non_ctry) if non_ctry else 0.0
    conf = c["base"] + c["agree_rules_weight"] * share
    if "TwnNm" in fields:
        conf += c["gazetteer_unchecked"] if unchecked else c["gazetteer_agree"]
    conf -= c["attempt_penalty"] * (attempt - 1)
    conf += c["model_confidence_weight"] * ((0.5 if model_conf is None else max(0.0, min(1.0, model_conf))) - 0.5)
    if unsupported:
        conf = min(conf, c["unsupported_cap"])
    return round(max(0.0, min(1.0, conf)), 4)


class RepairPipeline:
    def __init__(self, engine: RulesEngine, agent: RepairAgent | None, repo, routing: dict):
        self.engine, self.agent, self.repo, self.cfg = engine, agent, repo, routing

    # -- verification: code decides ----------------------------------------------------------------------------------
    def verify(self, candidate: Candidate, raw_lines, hint, rules) -> tuple[list[str], list[str], bool]:
        """(hard reasons, unsupported fields, town unchecked). Hard reasons: validator + grounding."""
        hard = validate(candidate)
        g = grounding.check(candidate, raw_lines, hint, rules, self.engine.gazetteer)
        hard += g.reasons
        country = candidate.fields.get("Ctry")
        unsupported, unchecked = support.unsupported_fields(candidate.fields, country, all_profiles().get(country), self.engine.gazetteer)
        return hard, unsupported, g.unchecked or unchecked

    # -- one payment ---------------------------------------------------------------------------------------------------
    def process(self, msg_id: str, raw_lines: list[str], country_hint: str | None = None) -> Outcome:
        claim: Claim = self.repo.claim(msg_id, raw_lines)
        if not claim.claimed:
            return Outcome(msg_id, "skipped", reasons=["ALREADY_HANDLED"])
        try:
            out = self._decide(msg_id, raw_lines, country_hint, claim.api_failures)
        except Exception as e:   # never raise: an internal error is a REVIEW with a reason, and the property tests look for it
            out = Outcome(msg_id, "review", REVIEW, reasons=[f"INTERNAL_ERROR:{type(e).__name__}"])
        failures = claim.api_failures + (1 if out.status == "retry_later" else 0)
        self.repo.finish(msg_id, out.status, out.route, out.address() if out.status == "repaired" else None, out.confidence,
                         out.attempts, out.cost_usd, out.reasons, failures, out.steps)
        return out

    def _decide(self, msg_id, raw_lines, hint, prior_failures) -> Outcome:
        rules = self.engine.parse(raw_lines, hint)
        base = dict(msg_id=msg_id, rules_route=rules.route)
        if rules.route == "ACCEPT":
            cand = Candidate(dict(rules.fields))
            hard, _, unchecked = self.verify(cand, raw_lines, hint, rules)
            if hard:
                return Outcome(**base, status="review", route=REVIEW, reasons=hard, source="rules")
            conf = compute_confidence(cand.fields, rules, 1, None, [], unchecked, self.cfg)
            if conf >= self.cfg["threshold"]:
                return Outcome(**base, status="repaired", route=REPAIRED, fields=cand.fields, confidence=conf, source="rules")
            return Outcome(**base, status="review", route=REVIEW, confidence=conf, reasons=["LOW_CONFIDENCE"], source="rules")
        if rules.route == "REVIEW":
            return Outcome(**base, status="review", route=REVIEW, reasons=["RULES_REVIEW"] + rules.route_reasons, source="rules_review")
        if self.agent is None:
            return Outcome(**base, status="review", route=REVIEW, reasons=["NO_AGENT"], source="none")
        return self._with_agent(msg_id, raw_lines, hint, rules, prior_failures, base)

    def _with_agent(self, msg_id, raw_lines, hint, rules, prior_failures, base) -> Outcome:
        total_cost, steps, feedback, previous = 0.0, [], None, None
        reasons: list[str] = []
        max_attempts = int(self.cfg["max_attempts"])
        for attempt in range(1, max_attempts + 1):
            ar: AttemptResult = self.agent.attempt(msg_id, attempt, raw_lines, hint, rules, total_cost, feedback, previous)
            total_cost += ar.cost_usd
            steps += ar.steps
            if ar.status == "api_unavailable":
                if prior_failures + 1 >= int(self.cfg["max_payment_tries"]):
                    return Outcome(**base, status="review", route=REVIEW, attempts=attempt, cost_usd=total_cost, steps=steps,
                                   reasons=["API_UNAVAILABLE"], source="agent")
                return Outcome(**base, status="retry_later", attempts=attempt, cost_usd=total_cost, steps=steps, reasons=["API_UNAVAILABLE"], source="agent")
            if ar.status in ("budget", "api_fatal", "refusal"):
                code = {"budget": "COST_BUDGET_EXCEEDED", "api_fatal": "API_ERROR", "refusal": "MODEL_REFUSED"}[ar.status]
                return Outcome(**base, status="review", route=REVIEW, attempts=attempt, cost_usd=total_cost, steps=steps, reasons=[code], source="agent")
            if ar.status != "submitted":
                code = {"tool_cap": "TOOL_CALL_CAP", "no_submission": "NO_SUBMISSION", "invalid_submission": "MALFORMED_SUBMISSION"}[ar.status]
                feedback, previous = [code] + ar.errors, None
                reasons = feedback
                continue
            sub = ar.submitted
            cand = Candidate.from_dict(sub["address"])
            hard, unsupported, unchecked = self.verify(cand, raw_lines, hint, rules)
            if not hard and not unsupported:
                conf = compute_confidence(cand.fields, rules, attempt, sub.get("confidence"), [], unchecked, self.cfg)
                if conf >= self.cfg["threshold"]:
                    return Outcome(**base, status="repaired", route=REPAIRED, fields=cand.fields, adr_lines=cand.adr_lines, confidence=conf,
                                   attempts=attempt, cost_usd=total_cost, steps=steps, source="agent")
                return Outcome(**base, status="review", route=REVIEW, confidence=conf, attempts=attempt, cost_usd=total_cost, steps=steps,
                               reasons=["LOW_CONFIDENCE"], source="agent")
            feedback = hard + [f"UNSUPPORTED_FIELD:{n}" for n in unsupported]
            previous = sub["address"]
            reasons = feedback
        return Outcome(**base, status="review", route=REVIEW, attempts=max_attempts, cost_usd=total_cost, steps=steps,
                       reasons=["ATTEMPTS_EXHAUSTED"] + reasons, source="agent")
