"""normalise: NFC, trim, collapse spaces. The original text is kept: values are cut from it, never rewritten."""
from agent.rules.base import Rule
from agent.rules.state import ParseState, tokenize


class NormaliseRule(Rule):
    id = "normalise"

    def run(self, state: ParseState) -> None:
        state.text, state.tokens = tokenize(state.raw_lines, int(self.ctx.config.get("wrap_limit", 70)))
        state.add_evidence("text", self.id, f"{len(state.tokens)} tokens from {len(state.raw_lines)} lines (NFC, spaces collapsed)")
