"""length (XSD maximum lengths), confidence, routing, and the hybrid fallback."""
from __future__ import annotations

import re

from agent.rules.base import Rule
from agent.rules.state import ACCEPT, ELIMINATION, NEEDS_LLM, REVIEW, Leftover, ParseState, SEP_COMMA
from agent.rules.xsd import V1_FIELDS


class LengthRule(Rule):
    id = "length"

    def run(self, state: ParseState) -> None:
        for name in list(state.fields):
            if name not in V1_FIELDS:
                continue
            spec = self.ctx.schema.elements.get(name)
            if spec is None:
                state.fields.pop(name)
                continue
            value = state.fields[name]
            too_long = spec.max_length is not None and len(value) > spec.max_length
            bad_pattern = spec.pattern is not None and not re.fullmatch(spec.pattern, value)
            if too_long or bad_pattern:
                state.drop_field(name, f"overlong:{name}" if too_long else f"invalid:{name}")
                state.add_evidence(name, self.id, f"dropped: longer than the XSD maximum of {spec.max_length}" if too_long
                                   else "dropped: does not match the XSD pattern")
                if name == "Ctry":
                    state.country = None


class ConfidenceRule(Rule):
    """Per-field confidence was set by the rules; here the address-level score and the leftover report."""
    id = "confidence"

    def run(self, state: ParseState) -> None:
        sig = self.ctx.config["signals"]
        free = [t.idx for t in state.tokens if t.idx not in state.roles]
        landmark = [t.idx for t in state.tokens if state.roles.get(t.idx) == "landmark"]
        for reason, idxs in (("unclaimed text", free), ("landmark (unlabelled by design)", landmark)):
            run: list[int] = []
            for i in sorted(idxs) + [None]:
                if run and (i is None or i != run[-1] + 1):
                    s, e = state.tokens[run[0]].start, state.tokens[run[-1]].end
                    state.leftovers.append(Leftover(state.text[s:e], s, e, reason))
                    run = []
                if i is not None:
                    run.append(i)
        state.leftovers.sort(key=lambda l: l.start)
        cap = sig["elimination_cap"]
        for name, how in state.basis.items():
            if how == ELIMINATION and name in state.confidence:
                state.confidence[name] = min(state.confidence[name], cap)  # left over, not recognised: never confident
        conf = min(state.confidence.values(), default=1.0)
        state.notes["field_floor"] = conf  # leftover text lowers the address score but never, by itself, sends it to REVIEW
        unresolved = [l for l in state.leftovers if l.reason == "unclaimed text"]
        conf -= sig["leftover_penalty"] * min(len(unresolved), 3)
        if any(l.reason.startswith("landmark") for l in state.leftovers):
            conf -= sig["landmark_penalty"]
        if "TwnNm" not in state.fields or "Ctry" not in state.fields:
            conf = min(conf, 0.3)
        state.address_confidence = round(max(conf, 0.0), 3)


class RoutingRule(Rule):
    id = "routing"

    def run(self, state: ParseState) -> None:
        th = self.ctx.config["thresholds"]
        review = [f for f in state.flags if f in ("country_conflict", "hint_conflict", "region_town_mismatch", "no_country", "country_ambiguous")]
        reasons = list(review)
        if "TwnNm" not in state.fields:
            reasons.append("no_town_written")
        if "Ctry" not in state.fields:
            reasons.append("no_country")
        if reasons or state.notes.get("field_floor", 1.0) < th["review"]:
            state.route = REVIEW
            state.notes["route_reasons"] = reasons or ["low_confidence"]
            return
        unresolved = [l for l in state.leftovers if l.reason == "unclaimed text"]
        overflow = [f for f in state.flags if f.startswith(("overlong:", "invalid:"))]
        low = (state.address_confidence or 0) < th["accept"]
        uncertain = [f for f in state.flags if f in ("partial_postcode", "town_unverified", "landmark_unbounded", "street_town_clash")]
        by_elimination = [f"by_elimination:{n}" for n, how in state.basis.items() if how == ELIMINATION]
        if unresolved or overflow or low or uncertain or by_elimination:
            state.route = NEEDS_LLM
            state.notes["route_reasons"] = (["unclaimed_text"] if unresolved else []) + overflow + (["low_confidence"] if low else []) \
                + uncertain + by_elimination
        else:
            state.route = ACCEPT
            state.notes["route_reasons"] = []


class HybridRule(Rule):
    """When the address is not fully structured: TwnNm and Ctry structured, the rest in AdrLine (at most max_adr_lines)."""
    id = "hybrid"

    def run(self, state: ParseState) -> None:
        if state.route == ACCEPT or "TwnNm" not in state.fields or "Ctry" not in state.fields:
            return
        max_lines = int(self.ctx.config["max_adr_lines"])
        line_max = int(self.ctx.config["adr_line_max"])
        town = set(state.field_tokens.get("TwnNm", [])) | set(state.field_tokens.get("Ctry", []))
        by_line: dict[int, list[str]] = {}
        for t in state.tokens:
            if t.idx not in town:
                by_line.setdefault(t.line, []).append(t.text)
        lines: list[str] = []
        for li in sorted(by_line):
            piece = " ".join(by_line[li])
            if lines and len(lines[-1]) + 1 + len(piece) <= line_max:
                lines[-1] += " " + piece
            else:
                lines.append(piece)
        if len(lines) > max_lines or any(len(l) > line_max for l in lines):
            state.hybrid = None
            state.flag("hybrid_too_long")
            return
        state.hybrid = {"TwnNm": state.fields["TwnNm"], "Ctry": state.fields["Ctry"], "AdrLine": lines}
