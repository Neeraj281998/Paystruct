"""locality: a clean leftover segment next to the town (IE, GB, IN). Other countries leave it as a leftover."""
from __future__ import annotations

from agent.rules.base import Rule, building_word_hit, country_name_keys, has_digit, is_street_word, token_gap
from agent.rules.state import ELIMINATION, EXPLICIT, ParseState


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
            if town and " ".join(t.fold for t in toks) == " ".join(state.tokens[i].fold for i in town):
                continue  # the town written twice is not a locality
            gap = token_gap(chunk[0], chunk[-1], town[0]) if town else 0
            if best is None or gap < best[0]:
                best = (gap, chunk)
        if best:
            chunk = best[1]
            text = state.text_of(chunk)
            if prof.locality_patterns and any(p.fullmatch(text) for p in prof.locality_patterns):
                state.claim("TwnLctnNm", chunk, self.id, "matches a locality pattern of the profile", self.ctx.config["signals"]["rule_set"] - 0.05)
            elif self.ctx.gazetteer.lookup(prof.code, text):
                state.claim("TwnLctnNm", chunk, self.id, "a place listed in the gazetteer, beside the town", self.ctx.config["signals"]["rule_set"] - 0.05)
            else:
                state.claim("TwnLctnNm", chunk, self.id, "unclaimed segment nearest the town, not a listed place",
                            self.ctx.config["signals"]["rule_set"] - 0.05, basis=ELIMINATION)


class LocalityPatternRule(Rule):
    """'Sector 12', 'Sec 12', 'Sector-12', 'Phase 2' are localities, not house numbers (guide section 18)."""
    id = "locality_pattern"

    def run(self, state: ParseState) -> None:
        prof = self.profile(state)
        if prof is None or not prof.locality_patterns or "TwnLctnNm" in state.fields:
            return
        for chunk in state.chunks():
            for a in range(len(chunk)):
                for b in range(min(len(chunk), a + 3), a, -1):
                    win = chunk[a:b]
                    text = state.text_of(win)
                    if any(p.fullmatch(text) for p in prof.locality_patterns):
                        state.claim("TwnLctnNm", win, self.id, f"'{text}' matches a locality pattern of the {prof.code} profile",
                                    self.ctx.config["signals"]["rule_set"] - 0.05)
                        return
