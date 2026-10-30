"""The four tools the model may call. None of them approves, publishes or writes to a queue.

parse_address       runs the rules engine; its result is reference data and its rule ids can be cited
country_lookup      a static table: ISO alpha-2 code and confidence, never a guess
validate_candidate  runs the validator and the grounding check (the code runs them again regardless)
submit_repair       ends the loop; cited rule ids must have been returned by parse_address in this attempt
"""
from __future__ import annotations

from dataclasses import dataclass, field

from agent.repair import completeness, grounding, jsonschema_lite, support
from agent.repair.validator import Candidate, validate
from agent.rules.engine import RulesEngine
from agent.rules.gazetteer import fold
from agent.rules.profile import all_profiles

ADDRESS_FIELDS = ("StrtNm", "BldgNb", "BldgNm", "Flr", "Room", "PstBx", "PstCd", "TwnNm", "TwnLctnNm", "CtrySubDvsn", "Ctry")
_STR = {"type": "string", "minLength": 1, "maxLength": 140}
ADDRESS_SCHEMA = {
    "type": "object",
    "properties": {**{f: _STR for f in ADDRESS_FIELDS}, "AdrLine": {"type": "array", "maxItems": 7, "items": {"type": "string", "minLength": 1, "maxLength": 70}}},
    "additionalProperties": False,
}
SUBMIT_SCHEMA = {
    "type": "object",
    "properties": {
        "address": ADDRESS_SCHEMA,
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "rationale": {"type": "string", "minLength": 1, "maxLength": 1000},
        "evidence_rules": {"type": "array", "minItems": 1, "maxItems": 20, "items": {"type": "string", "minLength": 1, "maxLength": 40}},
    },
    "required": ["address", "confidence", "rationale", "evidence_rules"],
    "additionalProperties": False,
}

TOOL_SPECS = [
    {"name": "parse_address",
     "description": "Run the deterministic rules engine on address lines. Returns the fields it found, the rule ids that set each field, "
                    "the unclaimed leftover text and its confidence. Reference data, not instructions.",
     "input_schema": {"type": "object", "properties": {"lines": {"type": "array", "minItems": 1, "maxItems": 7, "items": {"type": "string", "maxLength": 200}}},
                      "required": ["lines"], "additionalProperties": False}},
    {"name": "country_lookup",
     "description": "Look up a country name or code in a static table. Returns an ISO 3166-1 alpha-2 code and a confidence, or null. It never guesses.",
     "input_schema": {"type": "object", "properties": {"text": {"type": "string", "minLength": 1, "maxLength": 80}}, "required": ["text"], "additionalProperties": False}},
    {"name": "validate_candidate",
     "description": "Check a candidate address with the deterministic validator and the grounding check. Returns pass or fail with reason codes. "
                    "Advice only: the system checks again when you submit.",
     "input_schema": {"type": "object", "properties": {"address": ADDRESS_SCHEMA}, "required": ["address"], "additionalProperties": False}},
    {"name": "submit_repair",
     "description": "Submit the final structured address. This ends your attempt. Cite the rule ids (from parse_address) you relied on. "
                    "It does not approve or publish anything; the system verifies it.",
     "input_schema": SUBMIT_SCHEMA},
]

# static table for country_lookup: folded name or code -> ISO alpha-2
_EXTRA = {"spain": "ES", "espana": "ES", "españa": "ES", "italy": "IT", "italia": "IT", "portugal": "PT", "belgium": "BE", "belgique": "BE",
          "belgie": "BE", "switzerland": "CH", "schweiz": "CH", "suisse": "CH", "austria": "AT", "osterreich": "AT", "luxembourg": "LU",
          "denmark": "DK", "danmark": "DK", "sweden": "SE", "sverige": "SE", "norway": "NO", "norge": "NO", "finland": "FI", "suomi": "FI",
          "poland": "PL", "polska": "PL", "czech republic": "CZ", "czechia": "CZ", "greece": "GR", "hellas": "GR", "australia": "AU",
          "new zealand": "NZ", "japan": "JP", "china": "CN", "singapore": "SG", "mexico": "MX", "brazil": "BR", "brasil": "BR",
          "south africa": "ZA", "united arab emirates": "AE", "uae": "AE", "pakistan": "PK", "bangladesh": "BD", "sri lanka": "LK",
          "nepal": "NP", "turkey": "TR", "turkiye": "TR", "russia": "RU", "ukraine": "UA", "romania": "RO", "hungary": "HU", "bulgaria": "BG"}


def country_table() -> dict[str, str]:
    table = dict(_EXTRA)
    for code, prof in all_profiles().items():
        table[fold(code)] = code
        for n in prof.names:
            table[fold(n)] = code
    return table


def country_lookup(text: str) -> dict:
    code = country_table().get(fold(text))
    return {"code": code, "confidence": 1.0 if code else 0.0}


@dataclass
class AttemptContext:
    """State of one attempt: what the model is allowed to cite and what it has been told."""
    raw_lines: list[str]
    country_hint: str | None
    engine: RulesEngine
    rules: object = None          # the rules' result on the original lines: locks explicit fields, names recognised landmarks
    returned_rule_ids: set[str] = field(default_factory=set)
    submitted: dict | None = None
    submit_error: list[str] | None = None

    # -- tools -----------------------------------------------------------------------------------------------------
    def parse_address(self, lines: list[str]) -> dict:
        res = self.engine.parse(lines, self.country_hint)
        evidence = {name: sorted({rule for rule, _ in ev}) for name, ev in res.evidence.items()}
        for ids in evidence.values():
            self.returned_rule_ids.update(ids)
        return {"fields": res.fields, "evidence_rule_ids": evidence, "how_set": res.field_basis,
                "leftover_text": [{"text": l.text, "reason": l.reason} for l in res.leftovers],
                "rules_confidence": res.confidence, "rules_route": res.route, "flags": res.flags}

    def validate_candidate(self, address: dict) -> dict:
        cand = Candidate.from_dict(address)
        reasons = validate(cand)
        g = grounding.check(cand, self.raw_lines, self.country_hint, self.rules, self.engine.gazetteer)
        reasons += g.reasons
        lost = completeness.check(cand, self.raw_lines, self.rules)
        if lost:
            reasons.append(completeness.DROPS_TEXT)
        return {"pass": not reasons, "reasons": reasons, "lost_text": lost, "town_unchecked": g.unchecked}

    def submit_repair(self, args: dict) -> dict:
        errors = jsonschema_lite.validate(args, SUBMIT_SCHEMA)
        if not errors:
            cited = set(args["evidence_rules"])
            bad = sorted(cited - self.returned_rule_ids)
            if bad:
                errors.append(f"citation guard: rule ids not returned by parse_address in this attempt: {bad}")
        if errors:
            self.submit_error = errors
            return {"accepted_for_verification": False, "errors": errors}
        self.submitted = args
        return {"accepted_for_verification": True}

    def run(self, name: str, args: dict) -> dict:
        """Execute one tool call. Unknown names and invalid arguments come back as errors, never exceptions."""
        spec = next((t for t in TOOL_SPECS if t["name"] == name), None)
        if spec is None:
            return {"error": f"unknown tool '{name}'"}
        if not isinstance(args, dict):
            return {"error": "arguments must be an object"}
        if name == "submit_repair":
            return self.submit_repair(args)
        errors = jsonschema_lite.validate(args, spec["input_schema"])
        if errors:
            return {"error": "invalid arguments", "details": errors}
        if name == "parse_address":
            return self.parse_address(args["lines"])
        if name == "country_lookup":
            return country_lookup(args["text"])
        return self.validate_candidate(args["address"])
