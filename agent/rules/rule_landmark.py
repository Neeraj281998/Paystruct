"""landmarks (guide section 18): 'near City Mall' stays unlabelled; it is reported as leftover, never put in a field."""
from __future__ import annotations

from agent.rules.base import Rule
from agent.rules.state import ParseState, SEP_COMMA


class LandmarkRule(Rule):
    id = "landmark"

    def run(self, state: ParseState) -> None:
        prof = self.profile(state)
        if prof is None or not (prof.landmark_keywords or prof.landmark_suffixes):
            return
        n = len(state.tokens)
        i = 0
        while i < n:
            if not state.is_free(i):
                i += 1
                continue
            hit = None
            for kw in prof.landmark_keywords:
                words = kw.split()
                span = [i + k for k in range(len(words))]
                if span[-1] < n and all(state.is_free(k) for k in span) and [state.tokens[k].fold for k in span] == words:
                    hit = span
                    break
            if hit is None:
                i += 1
                continue
            end = hit[-1]
            while end + 1 < n and state.tokens[end].sep < SEP_COMMA and state.is_free(end + 1):
                end += 1
            idxs = list(range(i, end + 1))
            if state.tokens[end].sep < SEP_COMMA and len(idxs) > 2:
                state.flag("landmark_unbounded")  # ran to a claimed token or the end with no separator: where it stops is a guess
            state.mark("landmark", idxs, self.id, f"landmark phrase '{state.text_of(idxs)}' (not a structured field)")
            i = end + 1
        for chunk in state.chunks():
            folds = " ".join(state.tokens[k].fold for k in chunk)
            if any(folds.endswith(s) and len(chunk) > len(s.split()) for s in prof.landmark_suffixes):
                state.mark("landmark", chunk, self.id, "landmark phrase ending in 'ke paas'")
