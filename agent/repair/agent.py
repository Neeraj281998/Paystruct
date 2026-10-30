"""A hand-written tool-use loop on the Anthropic Messages API. No framework.

Limits are enforced here, in code, not in the prompt: tool calls per attempt, cost per payment, request timeout, bounded
retries with backoff on API errors. The model proposes; nothing in this module accepts a proposal.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import anthropic

from agent.repair import prompts
from agent.repair.config import Prices
from agent.repair.tools import TOOL_SPECS, AttemptContext
from agent.rules.engine import RulesEngine

RETRYABLE = (anthropic.APIConnectionError, anthropic.APITimeoutError, anthropic.RateLimitError, anthropic.InternalServerError)


class TransientApiError(Exception):
    """Raised by a test double to stand for an outage; treated like RETRYABLE."""


class ApiUnavailable(Exception):
    pass


class ApiFatal(Exception):
    pass


@dataclass
class Step:
    attempt: int
    step: int
    tool: str
    input: dict
    output: dict
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0


@dataclass
class AttemptResult:
    status: str                      # submitted | invalid_submission | no_submission | tool_cap | budget | api_unavailable | api_fatal | refusal
    submitted: dict | None = None
    errors: list[str] = field(default_factory=list)
    tool_calls: int = 0
    cost_usd: float = 0.0
    steps: list[Step] = field(default_factory=list)


def make_client(timeout_s: float):
    """The real client. It reads ANTHROPIC_API_KEY from the environment; the key is never read, stored or logged here."""
    return anthropic.Anthropic(timeout=timeout_s, max_retries=0)


def _to_param(block) -> dict:
    if hasattr(block, "model_dump"):
        return block.model_dump(exclude_none=True)
    return {k: v for k, v in vars(block).items() if not k.startswith("_")}


class RepairAgent:
    def __init__(self, client, engine: RulesEngine, model: str, routing: dict, prices: Prices, sleep=time.sleep, clock=time.perf_counter):
        self.client, self.engine, self.model, self.cfg, self.prices = client, engine, model, routing, prices
        self.sleep, self.clock = sleep, clock

    # -- one API call with bounded retries ---------------------------------------------------------------------------
    def _call(self, **kwargs):
        tries = int(self.cfg["api_retries"])
        delay = float(self.cfg["api_backoff_s"])
        for i in range(tries):
            try:
                return self.client.messages.create(**kwargs)
            except (*RETRYABLE, TransientApiError):
                if i == tries - 1:
                    raise ApiUnavailable("the API stayed unavailable")
                self.sleep(delay * (2 ** i))
            except anthropic.APIStatusError as e:   # 4xx other than 429: retrying will not help
                raise ApiFatal(f"API error {getattr(e, 'status_code', '?')}")
        raise ApiUnavailable("the API stayed unavailable")

    def attempt(self, msg_id: str, attempt_no: int, raw_lines: list[str], country_hint: str | None, rules, cost_so_far: float,
                feedback: list[str] | None = None, previous: dict | None = None) -> AttemptResult:
        cap = int(self.cfg["max_tool_calls"])
        budget = float(self.cfg["max_cost_usd_per_payment"])
        ctx = AttemptContext(raw_lines, country_hint, self.engine, rules=rules)
        rules_summary = {"fields": rules.fields, "evidence_rule_ids": {n: sorted({r for r, _ in ev}) for n, ev in rules.evidence.items()},
                         "how_set": rules.field_basis, "leftover_text": [l.text for l in rules.leftovers], "rules_confidence": rules.confidence}
        for ids in rules_summary["evidence_rule_ids"].values():
            ctx.returned_rule_ids.update(ids)        # the pre-run parse counts as parse_address having returned them
        tag = prompts.new_tag()
        messages = [{"role": "user", "content": prompts.first_user_message(raw_lines, country_hint, rules_summary, feedback, previous, tag)}]
        out = AttemptResult("no_submission")
        step_no = 0
        calls = 0
        for _turn in range(cap + 3):
            if cost_so_far + out.cost_usd >= budget:
                out.status = "budget"
                return out
            kwargs = dict(model=self.model, max_tokens=int(self.cfg["max_tokens"]), system=prompts.SYSTEM_PROMPT,
                          tools=TOOL_SPECS, messages=messages, output_config={"effort": self.cfg.get("effort", "low")})
            t0 = self.clock()
            try:
                resp = self._call(**kwargs)
            except ApiUnavailable:
                out.status = "api_unavailable"
                return out
            except ApiFatal as e:
                out.status, out.errors = "api_fatal", [str(e)]
                return out
            ms = int((self.clock() - t0) * 1000)
            tin, tout = int(resp.usage.input_tokens), int(resp.usage.output_tokens)
            out.cost_usd += self.prices.cost(self.model, tin, tout)
            step_no += 1
            blocks = list(resp.content)
            out.steps.append(Step(attempt_no, step_no, "llm_call", {"messages": len(messages)},
                                  {"stop_reason": resp.stop_reason, "blocks": [b.type for b in blocks]}, tin, tout, ms))
            if resp.stop_reason == "refusal":
                out.status = "refusal"
                return out
            uses = [b for b in blocks if b.type == "tool_use"]
            if not uses:
                out.status = "no_submission"
                return out
            messages.append({"role": "assistant", "content": [_to_param(b) for b in blocks]})
            results = []
            for use in uses:
                if calls >= cap:
                    out.status, out.tool_calls = "tool_cap", calls
                    return out
                calls += 1
                t1 = self.clock()
                try:
                    args = dict(use.input) if isinstance(use.input, dict) else use.input
                    result = ctx.run(use.name, args)
                except Exception as e:   # a tool bug must not break the loop; the model sees an error
                    result = {"error": f"tool failed: {type(e).__name__}"}
                step_no += 1
                out.steps.append(Step(attempt_no, step_no, use.name, args if isinstance(args, dict) else {"raw": str(args)}, result,
                                      0, 0, int((self.clock() - t1) * 1000)))
                if use.name == "submit_repair":
                    out.tool_calls = calls
                    if ctx.submitted is not None:
                        out.status, out.submitted = "submitted", ctx.submitted
                    else:
                        out.status, out.errors = "invalid_submission", list(ctx.submit_error or ["invalid submission"])
                    return out
                results.append({"type": "tool_result", "tool_use_id": use.id, "content": prompts.tool_result_text(result),
                                "is_error": "error" in result})
            messages.append({"role": "user", "content": results})
        out.status, out.tool_calls = "no_submission", calls
        return out
