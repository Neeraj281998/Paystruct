"""ParseState: tokens with character spans, fields found, evidence, confidence, leftovers and the route.

Offsets are character offsets into `state.text`, the raw lines (NFC) joined with "\\n".
"""
from __future__ import annotations

import copy
import re
import unicodedata
from dataclasses import dataclass, field

from agent.rules.gazetteer import fold

WORD = re.compile(r"\S+")
OPENERS = "([{\"“‘"
CLOSERS_SEP = ")]}"
TRAILING_STRIP = ",;:)]}\"”’"
PURE_SEPARATOR = re.compile(r"^[\W_]+$", re.UNICODE)

SEP_NONE, SEP_COMMA, SEP_LINE, SEP_COMMA_LINE = 0, 1, 2, 3  # the last: a comma and then a line break

ACCEPT, NEEDS_LLM, REVIEW = "ACCEPT", "NEEDS_LLM", "REVIEW"
# How a field was set. EXPLICIT: a pattern, a gazetteer match, a keyword or a country-profile word said so.
# ELIMINATION: it is what was left over after the other rules took their share.
EXPLICIT, ELIMINATION = "explicit", "elimination"


@dataclass(frozen=True)
class Token:
    idx: int
    text: str
    start: int
    end: int
    line: int
    sep: int  # separator after this token: 0 space, 1 comma/dash/bracket, 2 line break
    fold: str


@dataclass
class Evidence:
    rule: str
    why: str


def tokenize(lines: list[str], wrap_limit: int = 70) -> tuple[str, list[Token]]:
    """Split NFC-normalised lines into tokens. Commas, dashes, slashes and brackets become separators, not tokens."""
    lines = [unicodedata.normalize("NFC", l) for l in lines]
    text = "\n".join(lines)
    bases, pos = [], 0
    for l in lines:
        bases.append(pos)
        pos += len(l) + 1
    raw: list[list] = []  # [text, start, end, line, sep]
    for li, line in enumerate(lines):
        for m in WORD.finditer(line):
            word, start, end = m.group(), m.start(), m.end()
            if PURE_SEPARATOR.match(word):
                if raw and raw[-1][3] == li:
                    raw[-1][4] = max(raw[-1][4], SEP_COMMA)
                continue
            opened = False
            while word and word[0] in OPENERS:
                word, start, opened = word[1:], start + 1, True
            sep = SEP_NONE
            while word and word[-1] in TRAILING_STRIP:
                if word[-1] in ",;" or word[-1] in CLOSERS_SEP:
                    sep = SEP_COMMA
                word, end = word[:-1], end - 1
            if opened and raw and raw[-1][3] == li:
                raw[-1][4] = max(raw[-1][4], SEP_COMMA)
            if not word:
                if raw and raw[-1][3] == li:
                    raw[-1][4] = max(raw[-1][4], sep)
                continue
            raw.append([word, bases[li] + start, bases[li] + end, li, sep])
    tokens: list[Token] = []
    for i, (word, s, e, li, sep) in enumerate(raw):
        nxt = raw[i + 1] if i + 1 < len(raw) else None
        if nxt is not None and nxt[3] != li:
            # A line that ends where the next word would not have fitted was wrapped, not ended.
            wrapped = len(lines[li].strip()) + 1 + len(nxt[0]) > wrap_limit
            if not wrapped:
                sep = SEP_COMMA_LINE if sep == SEP_COMMA else SEP_LINE
        elif nxt is None:
            sep = SEP_COMMA_LINE if sep == SEP_COMMA else SEP_LINE
        tokens.append(Token(i, word, s, e, li, sep, fold(word)))
    return text, tokens


@dataclass
class Leftover:
    text: str
    start: int
    end: int
    reason: str


@dataclass
class ParseState:
    raw_lines: list[str]
    country_hint: str | None = None
    text: str = ""
    tokens: list[Token] = field(default_factory=list)
    roles: dict[int, str] = field(default_factory=dict)  # token index -> field or role that claimed it
    fields: dict[str, str] = field(default_factory=dict)
    field_tokens: dict[str, list[int]] = field(default_factory=dict)
    spans: dict[str, list[tuple[int, int]]] = field(default_factory=dict)
    evidence: dict[str, list[Evidence]] = field(default_factory=dict)
    confidence: dict[str, float] = field(default_factory=dict)
    basis: dict[str, str] = field(default_factory=dict)  # field -> EXPLICIT or ELIMINATION: how it was set
    country: str | None = None
    country_source: str | None = None
    flags: list[str] = field(default_factory=list)
    notes: dict = field(default_factory=dict)
    leftovers: list[Leftover] = field(default_factory=list)
    address_confidence: float | None = None
    route: str | None = None
    hybrid: dict | None = None

    # -- copying ---------------------------------------------------------------------------------------------------
    def copy(self) -> "ParseState":
        return copy.deepcopy(self)

    # -- token queries ---------------------------------------------------------------------------------------------
    def is_free(self, idx: int) -> bool:
        return idx not in self.roles

    def free_indexes(self) -> list[int]:
        return [t.idx for t in self.tokens if t.idx not in self.roles]

    def chunks(self, extra_break: bool = True) -> list[list[int]]:
        """Maximal runs of free tokens, broken at claimed tokens and after any comma or line break."""
        out: list[list[int]] = []
        cur: list[int] = []
        for t in self.tokens:
            if t.idx in self.roles:
                if cur:
                    out.append(cur)
                    cur = []
                continue
            cur.append(t.idx)
            if t.sep >= SEP_COMMA:
                out.append(cur)
                cur = []
        if cur:
            out.append(cur)
        return out

    def text_of(self, idxs: list[int]) -> str:
        return " ".join(self.tokens[i].text for i in idxs)

    # -- claiming --------------------------------------------------------------------------------------------------
    def flag(self, name: str) -> None:
        if name not in self.flags:
            self.flags.append(name)

    def add_evidence(self, key: str, rule: str, why: str) -> None:
        self.evidence.setdefault(key, []).append(Evidence(rule, why))

    def claim(self, name: str, idxs: list[int], rule: str, why: str, conf: float, value: str | None = None,
              basis: str = EXPLICIT) -> None:
        """Set field `name` from tokens `idxs` (written text, single-spaced). A field is set once."""
        idxs = sorted(idxs)
        if name in self.fields:
            raise ValueError(f"{name} already set")
        self.fields[name] = value if value is not None else self.text_of(idxs)
        self.field_tokens[name] = idxs
        self.spans[name] = self.spans_of(idxs)
        self.confidence[name] = conf
        self.basis[name] = basis
        for i in idxs:
            self.roles[i] = name
        self.add_evidence(name, rule, why + (" [by elimination]" if basis == ELIMINATION else ""))

    def mark(self, role: str, idxs: list[int], rule: str, why: str) -> None:
        """Claim tokens for a role that is not an output field (country text, landmark)."""
        for i in idxs:
            self.roles[i] = role
        self.add_evidence(role, rule, why)

    def drop_field(self, name: str, reason: str) -> None:
        for i in self.field_tokens.pop(name, []):
            self.roles.pop(i, None)
        self.fields.pop(name, None)
        self.spans.pop(name, None)
        self.confidence.pop(name, None)
        self.basis.pop(name, None)
        self.flag(reason)

    def spans_of(self, idxs: list[int]) -> list[tuple[int, int]]:
        spans: list[tuple[int, int]] = []
        run: list[int] = []
        for i in sorted(idxs):
            if run and i != run[-1] + 1:
                spans.append((self.tokens[run[0]].start, self.tokens[run[-1]].end))
                run = []
            run.append(i)
        if run:
            spans.append((self.tokens[run[0]].start, self.tokens[run[-1]].end))
        return spans

    def leftover_tokens(self) -> list[int]:
        return [t.idx for t in self.tokens if t.idx not in self.roles or self.roles[t.idx] == "landmark"]
