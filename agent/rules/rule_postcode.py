"""extract postcode: regex windows from the country profile, over tokens (a postcode may be split or lack its space)."""
from __future__ import annotations

from agent.rules.base import Rule, free_windows, is_street_word, window_text
from agent.rules.state import ParseState, SEP_COMMA, SEP_COMMA_LINE


class PostcodeRule(Rule):
    id = "postcode"

    def _candidates(self, state, prof, patterns):
        found = []
        for win in free_windows(state, prof.postcode_max_tokens, max_inner_sep=3):
            if any(state.tokens[k].sep == SEP_COMMA for k in win[:-1]):
                continue  # a comma inside a line separates fields; a comma at a line end may still hide a split postcode
            text = window_text(state, win)
            if any(p.fullmatch(text) for p in patterns):
                found.append(win)
        # keep the longest window at each start; overlapping windows compete on score
        found.sort(key=lambda w: (w[0], -len(w)))
        out, starts = [], set()
        for w in found:
            if w[0] in starts:
                continue
            starts.add(w[0])
            out.append(w)
        return out

    def _score(self, state, prof, win) -> float:
        last = win[-1]
        score = -4.0 if any(state.tokens[k].sep == SEP_COMMA_LINE for k in win[:-1]) else 0.0  # split over a comma and a line break
        nxt = state.tokens[last + 1] if last + 1 < len(state.tokens) else None
        prev = state.tokens[win[0] - 1] if win[0] > 0 else None
        if nxt is not None and state.tokens[last].sep == 0 and (is_street_word(prof, nxt) or nxt.fold in prof.building_words):
            score -= 3  # "12345 Main St": a house number, not a postcode
        if prev is not None and state.tokens[win[0] - 1].sep == 0 and prev.fold in {"no", "plot", "house", "door", "flat", "unit", "apt", "suite"}:
            score -= 3
        # next to a written town or region
        for k in (last + 1, win[0] - 1):
            if 0 <= k < len(state.tokens) and state.is_free(k):
                for n in (3, 2, 1):
                    span = list(range(k, k + n)) if k > last else list(range(k - n + 1, k + 1))
                    if span[0] < 0 or span[-1] >= len(state.tokens):
                        continue
                    phrase = " ".join(state.tokens[i].text for i in span)
                    if self.ctx.gazetteer.lookup(prof.code, phrase):
                        score += 2
                        break
        if prev is not None and prof.region_lookup().get(prev.fold):
            score += 2
        return score + 0.001 * win[0]  # later in the text wins ties

    def run(self, state: ParseState) -> None:
        prof = self.profile(state)
        if prof is None:
            return
        sig = self.ctx.config["signals"]
        cands = self._candidates(state, prof, prof.postcode_patterns)
        conf, kind = sig["postcode_full"], "full pattern"
        if not cands and prof.partial_patterns:
            cands = [w for w in self._candidates(state, prof, prof.partial_patterns)
                     if (state.tokens[w[-1]].sep >= SEP_COMMA or w[-1] + 1 >= len(state.tokens) or not state.is_free(w[-1] + 1))]
            conf, kind = sig["postcode_partial"], "partial pattern (routing key or outward code only)"
            if cands:
                state.flag("partial_postcode")
        if not cands:
            return
        scored = sorted(cands, key=lambda w: self._score(state, prof, w), reverse=True)
        best = scored[0]
        if len(cands) > 1 and kind == "full pattern":
            conf = sig["postcode_ambiguous"]
            kind += f" ({len(cands)} candidates, best by context)"
        state.claim("PstCd", best, self.id, f"{prof.code} postcode {kind}", conf)
