"""region: county, state or province, only when written, as written (labelling guide sections 4, 12, 16-18)."""
from __future__ import annotations

from agent.rules.gazetteer import fold
from agent.rules.base import Rule, free_windows, has_digit, is_street_word
from agent.rules.state import ParseState, SEP_COMMA


class RegionRule(Rule):
    id = "region"

    def run(self, state: ParseState) -> None:
        prof = self.profile(state)
        if prof is None or not prof.regions:
            return
        table = prof.region_lookup()
        pc_idx = state.field_tokens.get("PstCd", [])
        all_profiles = self.ctx.profiles.values()
        street_like = set().union(*(p.street_words_after | p.street_words_before | set(p.building_words) for p in all_profiles))
        cands = []
        n = len(state.tokens)
        for win in free_windows(state, 6, max_inner_sep=0):
            folds = [state.tokens[i].fold for i in win]
            key = " ".join(folds)
            prefix_len = 0
            if prof.region_prefixes and folds[0] in prof.region_prefixes and len(win) > 1:
                key, prefix_len = " ".join(folds[1:]), 1
            elif prof.region_requires_prefix:
                continue
            region = table.get(key)
            if region is None:
                continue
            first, last = win[0], win[-1]
            nxt = state.tokens[last + 1] if last + 1 < n else None
            prev = state.tokens[first - 1] if first > 0 else None
            if not prefix_len and nxt is not None and state.is_free(nxt.idx) and state.tokens[last].sep == 0 and (nxt.fold in street_like or is_street_word(prof, nxt)):
                continue  # "Washington Street"
            if not prefix_len and prev is not None and state.is_free(prev.idx) and state.tokens[first - 1].sep == 0 and (has_digit(prev) or prev.fold in street_like):
                continue  # "12 Georgia ..." / "Rue Alabama"
            is_abbr = key != fold(region.name)
            gap = min((abs(first - p) if p < first else abs(p - last) for p in pc_idx), default=99) - 1
            if is_abbr and not prefix_len:
                after_last = [t for t in state.tokens[last + 1:] if state.is_free(t.idx)]
                if gap > 1 and after_last:
                    continue  # a bare abbreviation counts only beside the postcode or at the end
            if not is_abbr and not prefix_len and self.ctx.gazetteer.lookup(prof.code, state.text_of(win)):
                # a region that is also a town ("Delhi", "Chandigarh"): only when another town is written too
                others = [w for w in free_windows(state, 3, max_inner_sep=0) if not set(w) & set(win)
                          and self.ctx.gazetteer.lookup(prof.code, state.text_of(w)) and not any(has_digit(state.tokens[i]) for i in w)]
                if not others:
                    continue
            cands.append((win, region, max(gap, 0), is_abbr))
        if not cands:
            return
        cands.sort(key=lambda c: (c[2], c[3], -c[0][0]))
        win, region, gap, is_abbr = cands[0]
        conf = self.ctx.config["signals"]["rule_set"] + (0.02 if gap <= 1 else -0.1)
        state.claim("CtrySubDvsn", win, self.id, f"{prof.code} region '{region.name}' written" + (", beside the postcode" if gap <= 1 else ""), conf)
