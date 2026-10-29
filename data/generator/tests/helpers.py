from __future__ import annotations

import re
from collections import Counter


def written_text(rec: dict) -> str:
    """The raw lines as one string: a line break (and the spaces around it) is one space, commas and semicolons are
    punctuation, not part of any value. Case and spacing inside a line are left exactly as written."""
    text = "\n".join(rec["raw_lines"])
    text = re.sub(r"[ \t]*\n[ \t]*", " ", text)
    return text.replace(",", "").replace(";", "")


def tokens(text: str) -> Counter:
    return Counter(text.split())


def is_contiguous_span(token_list: list[str], wanted: Counter) -> bool:
    """True if some run of neighbouring tokens has exactly the tokens in wanted (and wanted is not empty)."""
    total = sum(wanted.values())
    if total == 0:
        return False
    for start in range(len(token_list)):
        seen: Counter = Counter()
        for token in token_list[start:start + total]:
            seen[token] += 1
        if seen == wanted:
            return True
    return False


def appears_in_order(rec: dict, first: str, second: str) -> bool:
    """first, then second, with only whitespace between, in the written text."""
    return re.search(re.escape(rec["gold"][first]) + r"\s+" + re.escape(rec["gold"][second]), written_text(rec)) is not None
