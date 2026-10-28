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
