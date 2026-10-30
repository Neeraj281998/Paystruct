"""PO boxes, floors, and units/flats/rooms: keyword patterns from the country profile (guide sections 2, 7, 13-18)."""
from __future__ import annotations

from agent.rules.base import Rule, free_windows, window_text
from agent.rules.state import ParseState


class _PatternRule(Rule):
    field = ""
    attr = ""
    max_tokens = 4
    label = ""

    def run(self, state: ParseState) -> None:
        prof = self.profile(state)
        if prof is None or self.field in state.fields:
            return
        patterns = getattr(prof, self.attr)
        best = None
        for win in free_windows(state, self.max_tokens, max_inner_sep=0):
            text = window_text(state, win)
            if any(p.fullmatch(text) for p in patterns):
                if best is None or win[0] < best[0] or (win[0] == best[0] and len(win) > len(best)):
                    best = win
        if best:
            state.claim(self.field, best, self.id, f"{self.label} '{window_text(state, best)}' matches the {prof.code} profile",
                        self.ctx.config["signals"]["rule_set"])


class PoBoxRule(_PatternRule):
    id, field, attr, label = "pobox", "PstBx", "pobox_patterns", "PO box"


class FloorRule(_PatternRule):
    id, field, attr, label = "floor", "Flr", "floor_patterns", "floor"


class UnitRule(_PatternRule):
    id, field, attr, label = "unit", "Room", "unit_patterns", "unit, flat or room"
