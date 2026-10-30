"""detect country: explicit ISO code, then country name, then a postcode pattern unique to one country, then cues, then hint.

'CA' inside a US address is California, a state, never Canada (labelling guide section 16).
"""
from __future__ import annotations

import math

from agent.rules.base import Rule, free_windows, has_digit, window_text
from agent.rules.gazetteer import fold
from agent.rules.state import ParseState, SEP_COMMA, SEP_COMMA_LINE

W_CODE, W_NAME, W_PATTERN, W_REGION = 10.0, 8.0, 6.0, 3.0


class CountryRule(Rule):
    id = "country"

    # -- evidence collectors ---------------------------------------------------------------------------------------
    def _segment_start(self, state: ParseState, i: int) -> int:
        while i > 0 and state.tokens[i - 1].sep == 0:
            i -= 1
        return i

    def _name_hits(self, state: ParseState) -> list[tuple[str, list[int]]]:
        names = {}
        for code, prof in self.ctx.profiles.items():
            for n in prof.names:
                names[fold(n)] = code
        before_words = set().union(*(p.street_words_before for p in self.ctx.profiles.values()))
        region_names = {fold(r.name) for p in self.ctx.profiles.values() for r in p.regions}
        hits = []
        for win in free_windows(state, 4, max_inner_sep=0):
            key = " ".join(state.tokens[i].fold for i in win)
            code = names.get(key)
            if not code:
                continue
            first, last = win[0], win[-1]
            if any(" ".join(state.tokens[k].fold for k in range(first - back, last + 1)) in region_names
                   for back in (1, 2) if first - back >= 0 and all(state.tokens[k].sep == 0 for k in range(first - back, last))):
                continue  # "Northern Ireland" is a region of the UK, not Ireland
            seg_start = self._segment_start(state, first)
            at_end = state.tokens[last].sep >= SEP_COMMA
            if not at_end:
                continue
            if first != seg_start:
                # inside a segment: reject when a type-first street word precedes with no digit between ("Rue Anatole France")
                bad = False
                for k in range(first - 1, seg_start - 1, -1):
                    t = state.tokens[k]
                    if has_digit(t):
                        break
                    if t.fold in before_words:
                        bad = True
                        break
                if bad:
                    continue
            hits.append((code, win))
        return hits

    def _code_hits(self, state: ParseState) -> list[tuple[str, list[int]]]:
        hits = []
        all_lower = not any(c.isupper() for c in state.text)
        for t in state.tokens:
            code = t.text.upper()
            if code in self.ctx.profiles and (t.text == code or all_lower) and state.is_free(t.idx):
                if t.sep < SEP_COMMA:
                    continue
                if self._is_state_not_country(state, t.idx, code):
                    continue
                hits.append((code, [t.idx]))
        return hits

    def _is_state_not_country(self, state: ParseState, idx: int, code: str) -> bool:
        """'Fort Wayne, IN' is Indiana, not India: the code is a US state and the town before it is listed there."""
        us = self.ctx.profiles.get("US")
        if us is None or code == "US" or idx == 0:
            return False
        region = us.region_lookup().get(fold(code))
        if region is None:
            return False
        prev_texts = [state.tokens[k].text for k in range(max(0, idx - 3), idx)]
        for n in (3, 2, 1):
            if len(prev_texts) >= n:
                phrase = " ".join(prev_texts[-n:])
                if code in self.ctx.gazetteer.admin1_codes("US", phrase):
                    return True
        return False

    def _covered_by_keywords(self, state: ParseState) -> set[int]:
        """Tokens that belong to a PO box, floor or unit in some profile: "Postfach 540722" is not an Indian PIN."""
        covered: set[int] = set()
        for prof in self.ctx.profiles.values():
            patterns = prof.pobox_patterns + prof.unit_patterns + prof.floor_patterns
            for win in free_windows(state, 4, max_inner_sep=0):
                if any(p.fullmatch(window_text(state, win)) for p in patterns):
                    covered |= set(win)
        return covered

    def _pattern_hits(self, state: ParseState) -> dict[str, int]:
        found: dict[str, int] = {}
        covered = self._covered_by_keywords(state)
        for code, prof in self.ctx.profiles.items():
            if not prof.postcode_patterns:
                continue
            for win in free_windows(state, prof.postcode_max_tokens, max_inner_sep=2):
                if any(state.tokens[k].sep in (SEP_COMMA, SEP_COMMA_LINE) for k in win[:-1]) or covered & set(win):
                    continue
                text = " ".join(state.tokens[i].text for i in win)
                if any(p.fullmatch(text) for p in prof.postcode_patterns):
                    found[code] = found.get(code, 0) + 1
                    break
        return found

    def _region_hits(self, state: ParseState) -> dict[str, float]:
        score: dict[str, float] = {}
        for code, prof in self.ctx.profiles.items():
            table = prof.region_lookup()
            for win in free_windows(state, 4, max_inner_sep=0):
                key = " ".join(state.tokens[i].fold for i in win)
                region = table.get(key)
                if region and len(key) > 3 and key == fold(region.name):
                    score[code] = max(score.get(code, 0), W_REGION)
        return score

    def _cue_scores(self, state: ParseState, candidates: list[str]) -> dict[str, float]:
        profs = self.ctx.profiles
        words: dict[str, set[str]] = {c: set() for c in profs}
        for c, p in profs.items():
            words[c] = p.street_words_after | p.street_words_before | set(p.building_words)
        scores = {c: 0.0 for c in candidates}
        for t in state.tokens:
            for c in candidates:
                p = profs[c]
                if t.fold in words[c]:
                    owners = sum(1 for o in profs if t.fold in words[o])
                    scores[c] += 1.0 / owners
                elif any(len(t.fold) > len(s) and t.fold.endswith(s) for s in p.street_suffixes):
                    scores[c] += 1.5
        for c in candidates:
            seen = set()
            best_pop = 0.0
            for win in free_windows(state, 3, max_inner_sep=0):
                key = " ".join(state.tokens[i].fold for i in win)
                if key in seen:
                    continue
                place = self.ctx.gazetteer.lookup(c, key)
                if place and not any(has_digit(state.tokens[i]) for i in win):
                    seen.add(key)
                    best_pop = max(best_pop, math.log10(place.population + 1))
            scores[c] += min(len(seen), 2) * 1.0 + 0.1 * best_pop
        return scores

    # -- decision --------------------------------------------------------------------------------------------------
    def run(self, state: ParseState) -> None:
        sig = self.ctx.config["signals"]
        votes: dict[str, float] = {}
        kind: dict[str, str] = {}
        tokens_for: dict[str, list[int]] = {}
        why: dict[str, str] = {}

        def vote(code, weight, k, reason, idxs=None):
            votes[code] = votes.get(code, 0) + weight
            if k_rank(k) > k_rank(kind.get(code, "")):
                kind[code] = k
                why[code] = reason
            if idxs and (k in ("code", "name")) and code not in tokens_for:
                tokens_for[code] = idxs

        def k_rank(k):
            return {"": 0, "hint": 1, "cues": 2, "region": 3, "pattern": 4, "name": 5, "code": 6}[k]

        for code, win in self._code_hits(state):
            vote(code, W_CODE, "code", f"ISO code {code} written at the end of a segment", win)
        for code, win in self._name_hits(state):
            vote(code, W_NAME, "name", f"country name '{window_text(state, win)}'", win)
        patterns = self._pattern_hits(state)
        unique = [c for c in patterns if self.ctx.profiles[c].postcode_unique]
        for c in unique:
            vote(c, W_PATTERN, "pattern", "postcode pattern matches only this country")
        for c, w in self._region_hits(state).items():
            vote(c, w, "region", "region name written")
        strong = {c for c in votes if kind[c] in ("code", "name", "pattern")}

        candidates = [c for c in patterns if c not in unique] or []
        if not strong:
            pool = candidates or list(self.ctx.profiles)
            cues = self._cue_scores(state, pool)
            ranked = sorted(cues.items(), key=lambda kv: -kv[1])
            if ranked and ranked[0][1] > 0:
                margin = ranked[0][1] - (ranked[1][1] if len(ranked) > 1 else 0)
                top = ranked[0][0]
                vote(top, ranked[0][1] + (1 if top in candidates else 0), "cues", f"street words, towns and region names favour {top} ({ranked[0][1]:.1f})")
                if margin < 0.75:
                    state.flag("country_ambiguous")
                    state.notes["country_margin"] = round(margin, 2)
        hint = state.country_hint
        if hint and hint in self.ctx.profiles:
            vote(hint, 2.0, "hint", "country hint from the message")
        if not votes:
            state.add_evidence("Ctry", self.id, "no country evidence")
            state.flag("no_country")
            return
        # strong evidence (code, name, unique pattern) decides, best kind first; otherwise the most votes
        chosen = max(votes, key=lambda c: (k_rank(kind[c]) >= 4, k_rank(kind[c]) if k_rank(kind[c]) >= 4 else 0, votes[c]))
        if kind[chosen] in ("cues", "region") and hint in self.ctx.profiles:
            chosen = hint  # a hint beats weak cues
        strong_others = [c for c in strong if c != chosen]
        if kind[chosen] in ("code", "name", "pattern") and strong_others:
            state.flag("country_conflict")
            state.add_evidence("Ctry", self.id, "conflicting country evidence: " + ", ".join(sorted(strong)))
        elif hint and hint in self.ctx.profiles and hint != chosen:
            state.flag("hint_conflict")
        state.country = chosen
        state.country_source = kind[chosen]
        state.fields["Ctry"] = chosen
        conf_key = {"code": "country_code", "name": "country_name", "pattern": "country_pattern", "region": "country_cues",
                    "cues": "country_cues", "hint": "country_hint"}[kind[chosen]]
        conf = sig[conf_key]
        if hint == chosen and kind[chosen] != "hint":
            conf = 1 - (1 - conf) * (1 - sig["country_hint"])  # two independent signals agree
            state.notes["hint_agrees"] = True
            if "country_ambiguous" in state.flags:
                state.flags.remove("country_ambiguous")
        state.confidence["Ctry"] = conf
        idxs = tokens_for.get(chosen, [])
        if idxs:
            state.mark("country", idxs, self.id, why[chosen])
            state.spans["Ctry"] = state.spans_of(idxs)
            state.field_tokens["Ctry"] = idxs
        else:
            state.spans["Ctry"] = []
        state.add_evidence("Ctry", self.id, why[chosen])
