"""street and building number split, per the country profile, plus building names (guide sections 3, 12-18)."""
from __future__ import annotations

from agent.rules.base import Rule, building_word_hit, has_digit, is_number, is_street_word, window_text
from agent.rules.profile import Profile
import re

from agent.rules.state import ELIMINATION, EXPLICIT, ParseState


class StreetRule(Rule):
    id = "street"

    # -- helpers ---------------------------------------------------------------------------------------------------
    def _has_street_word(self, prof: Profile, toks) -> bool:
        return any(is_street_word(prof, t) for t in toks)

    def _building(self, prof: Profile, toks) -> bool:
        return building_word_hit(prof, [t.fold for t in toks])

    def _street_span(self, prof: Profile, idxs: list[int], state: ParseState):
        """The part of `idxs` that is the street name, or None. Street type first (FR, CA-fr) or last (IE, GB, US, ...)."""
        toks = [state.tokens[i] for i in idxs]
        if not toks:
            return None, 0
        if toks[0].fold in prof.street_words_before and len(toks) > 1:
            return idxs, 0
        last = None
        for k, t in enumerate(toks):
            if t.fold in prof.street_words_after or (prof.street_suffixes and is_street_word(prof, t)):
                last = k
        if last is None:
            return None, 0
        end = last
        while end + 1 < len(toks) and toks[end + 1].fold in prof.street_trailing:
            end += 1
        return idxs[: end + 1], len(idxs) - end - 1

    def _split_building_street(self, state, prof, idxs):
        """'Hamilton Lodge Victoria Ave.': a building name then a street with no separator. (building, rest) or None."""
        toks = [state.tokens[i] for i in idxs]
        folds = [t.fold for t in toks]
        best = None
        if "BldgNm" not in state.fields:
            for k in range(1, len(toks)):  # type-first streets (FR, CA): "Résidence Le Central Rue du Château"
                if toks[k].fold in prof.street_words_before and len(toks) - k >= 2 and self._building(prof, toks[:k]):
                    return idxs[:k], idxs[k:]
        for k in range(len(toks) - 2):
            joined_to_k = " " + " ".join(folds[: k + 1]) + " "
            ends_building = any(joined_to_k.endswith(" " + w + " ") for w in prof.building_words)
            if ends_building and "BldgNm" not in state.fields:
                rest = idxs[k + 1:]
                span, _ = self._street_span(prof, rest, state)
                if span and len(span) >= 2 and not self._building(prof, [state.tokens[i] for i in span[:1]]):
                    best = (idxs[: k + 1], rest)
        return best

    _ORDINAL = re.compile(r"\d+(?:st|nd|rd|th|e|er|re|ème|eme|de|ste|°)?", re.IGNORECASE)

    def _claim_street(self, state, idxs, why, conf, explicit=True):
        """A street found by a street word is explicit, unless it holds a token like '263-II' that no rule recognises."""
        basis = EXPLICIT if explicit else ELIMINATION
        odd = [state.tokens[i].text for i in idxs if has_digit(state.tokens[i]) and not self._ORDINAL.fullmatch(state.tokens[i].text)]
        if odd:
            basis, why = ELIMINATION, why + f"; unrecognised token {odd[0]!r} inside it"
        state.claim("StrtNm", idxs, self.id, why, conf, basis=basis)

    def _claim_building_nb(self, state, prof, nb_idxs, why):
        if "BldgNb" not in state.fields:
            state.claim("BldgNb", nb_idxs, self.id, why, self.ctx.config["signals"]["rule_set"])

    # -- passes ----------------------------------------------------------------------------------------------------
    def _keyword_numbers(self, state: ParseState, prof: Profile) -> None:
        """IN: 'Plot 12', 'House No. 45', 'Door No. 12-3-45' go to BldgNb with their keyword (guide section 18)."""
        if not prof.bldgnb_patterns or "BldgNb" in state.fields:
            return
        for chunk in state.chunks():
            for a in range(len(chunk)):
                for b in range(min(len(chunk), a + 4), a, -1):
                    win = chunk[a:b]
                    if any(p.fullmatch(window_text(state, win)) for p in prof.bldgnb_patterns):
                        state.claim("BldgNb", win, self.id, f"number with its keyword '{window_text(state, win)}'",
                                    self.ctx.config["signals"]["rule_set"])
                        return

    def _chunk_before(self, state: ParseState, prof: Profile, chunk: list[int]) -> None:
        sig = self.ctx.config["signals"]
        toks = [state.tokens[i] for i in chunk]
        num_k = None
        if "BldgNb" not in state.fields:
            for k, t in enumerate(toks):
                if is_number(prof, t):
                    num_k = k
                    break
        if num_k is not None:
            nb = [chunk[num_k]]
            if num_k + 1 < len(toks) and toks[num_k + 1].fold in prof.number_suffix_words:
                nb.append(chunk[num_k + 1])
            rest = chunk[num_k + len(nb):]
            pre = chunk[:num_k]
            if "BldgNb" not in state.fields:
                a, _, b = toks[num_k].text.partition("-")
                if prof.unit_prefix_number and a.isdigit() and b.isdigit() and "Room" not in state.fields:
                    state.claim("Room", nb, self.id, "unit-number prefix in '5-123 Main St' (guide section 16)", sig["rule_set"], value=a)
                    state.claim("BldgNb", nb, self.id, "house number after the unit prefix", sig["rule_set"], value=b)
                else:
                    state.claim("BldgNb", nb, self.id, f"number '{window_text(state, nb)}' before the street", sig["rule_set"])
            if pre and self._building(prof, [state.tokens[i] for i in pre]) and "BldgNm" not in state.fields:
                state.claim("BldgNm", pre, self.id, "building word before the number", sig["rule_set"])
            self._street_from(state, prof, rest)
            return
        # no number in this chunk
        if self._has_street_word(prof, toks) or toks[0].fold in prof.street_words_before:
            self._street_from(state, prof, chunk)
        elif self._building(prof, toks) and "BldgNm" not in state.fields:
            state.claim("BldgNm", chunk, self.id, "building word", sig["rule_set"])

    def _street_from(self, state, prof, rest) -> None:
        sig = self.ctx.config["signals"]
        if not rest:
            return
        if "StrtNm" in state.fields:
            if "BldgNm" not in state.fields and self._building(prof, [state.tokens[i] for i in rest]):
                state.claim("BldgNm", rest, self.id, "building word after the number", sig["rule_set"])
            return
        split = self._split_building_street(state, prof, rest)
        if split:
            state.claim("BldgNm", split[0], self.id, "building word, then the street (no separator)", sig["rule_set"])
            rest = split[1]
        span, _ = self._street_span(prof, rest, state)
        toks = [state.tokens[i] for i in rest]
        if span:
            self._claim_street(state, span, "street word found", sig["street_word"])
        elif self._building(prof, toks) and "BldgNm" not in state.fields:
            state.claim("BldgNm", rest, self.id, "building word after the number", sig["rule_set"])
        elif not any(has_digit(t) for t in toks) and len(rest) <= 5:
            self._claim_street(state, rest, "name after a house number, no street word (guide 21.1)", sig["street_no_word"], explicit=False)

    def _peel_building_after(self, state, prof, street):
        """DE/NL: 'Gebouw West Pluijmplein' - a building name before the street-suffixed word (and its particles)."""
        toks = [state.tokens[i] for i in street]
        s = None
        for k, t in enumerate(toks):
            if is_street_word(prof, t):
                s = k
        if s is None or s == 0 or "BldgNm" in state.fields:
            return street
        start = s
        while start - 1 >= 0 and toks[start - 1].fold in prof.street_particles:
            start -= 1
        if start > 0 and self._building(prof, toks[:start]):
            state.claim("BldgNm", street[:start], self.id, "building word before the street", self.ctx.config["signals"]["rule_set"])
            return street[start:]
        return street

    def _chunk_after(self, state: ParseState, prof: Profile, chunk: list[int]) -> None:
        """DE and NL: the number follows the street."""
        sig = self.ctx.config["signals"]
        toks = [state.tokens[i] for i in chunk]
        if self._building(prof, toks) and not any(is_street_word(prof, t) for t in toks):
            if "BldgNm" not in state.fields:
                state.claim("BldgNm", chunk, self.id, "building word", sig["rule_set"])
            return
        num_k = None
        if "BldgNb" not in state.fields:
            for k in range(len(toks) - 1, 0, -1):
                if is_number(prof, toks[k]):
                    num_k = k
                    break
        if num_k is not None and "StrtNm" not in state.fields:
            street = chunk[:num_k]
            street = self._peel_building_after(state, prof, street)
            sw = any(is_street_word(prof, state.tokens[i]) for i in street)
            self._claim_street(state, street, "street word found" if sw else "name before the house number",
                               sig["street_word"] if sw else sig["street_no_word"], explicit=sw)
            state.claim("BldgNb", [chunk[num_k]], self.id, f"number '{toks[num_k].text}' after the street", sig["rule_set"])
        elif "StrtNm" not in state.fields and any(is_street_word(prof, t) for t in toks):
            street = self._peel_building_after(state, prof, chunk)
            self._claim_street(state, street, "street word found, no number", sig["street_word"])

    def run(self, state: ParseState) -> None:
        prof = self.profile(state)
        if prof is None:
            return
        self._keyword_numbers(state, prof)
        for chunk in state.chunks():
            chunk = [i for i in chunk if state.is_free(i)]
            if not chunk:
                continue
            if prof.number_position == "after":
                self._chunk_after(state, prof, chunk)
            else:
                self._chunk_before(state, prof, chunk)
