"""town: the gazetteer checks a town that is WRITTEN in the text, searched near the postcode and region first.

It never supplies a town. With no written town, TwnNm stays unset and the address goes to REVIEW (guide section 20).
"""
from __future__ import annotations

import math

from agent.rules.base import Rule, building_word_hit, country_name_keys, has_digit, is_street_word, token_gap
from agent.rules.gazetteer import fold
from agent.rules.state import ELIMINATION, ParseState, SEP_COMMA


class TownRule(Rule):
    id = "town"

    def _refs(self, state: ParseState) -> list[int]:
        refs = []
        for name in ("PstCd", "CtrySubDvsn"):
            refs += state.field_tokens.get(name, [])
        return refs

    def _extend(self, state, prof, phrase_fold, last):
        """Add an arrondissement, Dublin district or Cedex suffix that is written after the town."""
        n = len(state.tokens)
        for suf in prof.town_suffixes:
            if suf["towns"] and phrase_fold not in suf["towns"]:
                continue
            for k in range(suf["tokens"], 0, -1):
                span = list(range(last + 1, last + 1 + k))
                if span and span[-1] < n and all(state.is_free(i) for i in span) and all(state.tokens[i].sep == 0 for i in [last] + span[:-1]):
                    text = " ".join(state.tokens[i].text for i in span)
                    if suf["re"].fullmatch(text):
                        return span
        return []

    def _street_phrase(self, state, prof, i) -> str:
        """Is a candidate starting at token i inside a street name? 'out', 'in', or 'clash'.

        A type word that is both English-last and French-first (Boulevard, Place, Avenue in Canada) is read by position:
        with a name before it ("Williams Boulevard") it ends the street, so the town after it is a town; right after a
        number or at the start of a segment ("123 Boulevard Winnipeg") it opens a street, which is a clash.
        """
        k = i - 1
        while k >= 0 and state.tokens[k].sep == 0 and state.is_free(k):
            t = state.tokens[k]
            if t.fold in prof.street_words_before:
                if t.fold in prof.street_words_after:
                    name_before = k - 1 >= 0 and state.tokens[k - 1].sep == 0 and state.is_free(k - 1) and not has_digit(state.tokens[k - 1])
                    return "out" if name_before else "clash"
                return "in"
            k -= 1
        return "out"

    def _excluded(self, state, prof, i, j):
        """True: not a town. False: may be. 'clash': may be, but the street/town split is unclear (flag it)."""
        n = len(state.tokens)
        nxt = state.tokens[j + 1] if j + 1 < n else None
        prev = state.tokens[i - 1] if i > 0 else None
        if is_street_word(prof, state.tokens[j]):
            return True  # "Street" is a town in Somerset, but here it ends a street name
        after_ref = prev is not None and state.roles.get(prev.idx) in ("PstCd", "CtrySubDvsn")
        if nxt is not None and state.tokens[j].sep == 0 and state.is_free(j + 1) and not after_ref:
            if is_street_word(prof, nxt) or nxt.fold in prof.building_words:
                return True
            if any(nxt.fold == w.split()[0] for w in prof.building_words):
                return True
        if prev is not None and state.tokens[i - 1].sep == 0 and state.is_free(i - 1):
            if prev.fold in prof.building_words:
                return True
            if prev.fold in prof.street_words_before and prev.fold not in prof.street_words_after:
                return True
        refs = set(self._refs(state))
        adjacent_ref = (i - 1 in refs and state.tokens[i - 1].sep == 0) or (j + 1 in refs and state.tokens[j].sep == 0)
        where = self._street_phrase(state, prof, i)
        if where == "in":
            return not adjacent_ref  # "Moulin Grenoble 38000": written right against the postcode, so a town
        if where == "clash":
            return "clash" if adjacent_ref else True
        return False

    def run(self, state: ParseState) -> None:
        prof = self.profile(state)
        if prof is None or "TwnNm" in state.fields:
            return
        gaz, sig = self.ctx.gazetteer, self.ctx.config["signals"]
        refs = self._refs(state)
        n = len(state.tokens)
        cands = []
        for i in range(n):
            if not state.is_free(i):
                continue
            for length in (4, 3, 2, 1):
                j = i + length - 1
                if j >= n or not all(state.is_free(k) for k in range(i, j + 1)):
                    continue
                if any(state.tokens[k].sep >= SEP_COMMA for k in range(i, j)):
                    continue
                if any(has_digit(state.tokens[k]) for k in range(i, j + 1)):
                    continue
                phrase = " ".join(state.tokens[k].text for k in range(i, j + 1))
                place = gaz.lookup(prof.code, phrase)
                verdict = self._excluded(state, prof, i, j) if place is not None else True
                if verdict is True:
                    continue
                span = list(range(i, j + 1)) + self._extend(state, prof, fold(phrase), j)
                gap = min((token_gap(i, span[-1], r) for r in refs), default=0)
                score = -0.8 * gap + 0.5 * math.log10(place.population + 1) + 0.2 * length + 0.01 * i
                cands.append((score, span, place, phrase, verdict == "clash"))
        if cands:
            cands.sort(key=lambda c: -c[0])
            _, span, place, phrase, clash = cands[0]
            if clash:
                state.flag("street_town_clash")
            conf = sig["town_gazetteer"]
            why = f"'{phrase}' is listed in the {prof.code} gazetteer" + (f" (population {place.population})" if place.population else "")
            region = state.fields.get("CtrySubDvsn")
            if prof.admin1_is_abbr and region:
                reg = prof.region_lookup().get(fold(region))
                if reg and reg.abbr and reg.abbr[0] not in gaz.admin1_codes(prof.code, phrase):
                    state.flag("region_town_mismatch")
                    conf = 0.4
                    why += f"; but not under region {reg.abbr[0]}"
            state.claim("TwnNm", span, self.id, why, conf)
            return
        self._unverified(state, prof, refs, sig)

    def _unverified(self, state, prof, refs, sig) -> None:
        """A written town that the gazetteer does not list: only a clean segment right beside the postcode or region."""
        n = len(state.tokens)
        best = None
        for chunk in state.chunks():
            toks = [state.tokens[k] for k in chunk]
            if len(chunk) > 3 or any(has_digit(t) for t in toks) or " ".join(t.fold for t in toks) in country_name_keys(self.ctx.profiles):
                continue
            if sum(len(t.text) for t in toks) < 3:
                continue
            if any(is_street_word(prof, t) for t in toks) or building_word_hit(prof, [t.fold for t in toks]):
                continue
            if any(t.fold in prof.region_prefixes for t in toks):
                continue
            gap = min((token_gap(chunk[0], chunk[-1], r) for r in refs), default=99)
            if gap > 1:
                continue
            if best is None or gap < best[0]:
                best = (gap, chunk)
        if best:
            state.claim("TwnNm", best[1], self.id, "written beside the postcode, but not found in the gazetteer", sig["town_unverified"],
                        basis=ELIMINATION)
            state.flag("town_unverified")
