"""locality: a clean leftover segment next to the town (IE, GB, IN). Other countries leave it as a leftover."""
from __future__ import annotations

from agent.rules.base import Rule, building_word_hit, country_name_keys, has_digit, is_street_word, token_gap
from agent.rules.state import ParseState


class LocalityRule(Rule):
    id = "locality"

    def run(self, state: ParseState) -> None:
        prof = self.profile(state)
        if prof is None or not prof.localities or "TwnLctnNm" in state.fields:
            return
        town = state.field_tokens.get("TwnNm")
        best = None
        for chunk in state.chunks():
            toks = [state.tokens[i] for i in chunk]
            text = " ".join(t.text for t in toks)
            if len(chunk) > 4 or len(text) < 3 or " ".join(t.fold for t in toks) in country_name_keys(self.ctx.profiles):
                continue
            if any(has_digit(t) for t in toks) and not any(p.fullmatch(text) for p in prof.locality_patterns):
                continue
            if any(is_street_word(prof, t) for t in toks) or building_word_hit(prof, [t.fold for t in toks]):
                continue
            gap = token_gap(chunk[0], chunk[-1], town[0]) if town else 0
            if best is None or gap < best[0]:
                best = (gap, chunk)
        if best:
            state.claim("TwnLctnNm", best[1], self.id, "unclaimed segment nearest the town", self.ctx.config["signals"]["rule_set"] - 0.05)
