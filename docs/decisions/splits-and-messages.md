# Splits, frozen test set, hard-set format and message builder

Status: accepted (Phase 2B)

## Decisions

- **Disjoint by construction and by check.** Each generated split draws record numbers from its own range (dev 0, calibration 10,000, test 20,000 per country), so ids never repeat. A record is also skipped if its ground truth (country plus gold, case-folded, whitespace collapsed) was already taken, in any split. `scripts/check_splits.py` proves it afterwards.
- **The check never parses the frozen test split.** `data/splits/splits.manifest.json` stores a SHA-256 of each split's address keys (hashes and counts only, no addresses), written when the splits are built. The check compares those hashes and ties `test.jsonl` to the manifest by its file hash. Trade-off: the test addresses are proved disjoint through what the builder recorded, not by re-reading the file. `--include-test-file` parses it for the project owner.
- **Freeze.** `data/splits/test.sha256` holds the hash of `test.jsonl`; `scripts/verify_frozen.py` (standard library only) fails if the bytes change. `build_splits.py` never rewrites the test file once the hash exists, and stops if a rebuild would differ. Only `build_splits.py --refreeze` replaces it, and that needs the project owner's explicit approval each time.
- **Balance.** Countries get equal shares. Tiers rotate inside each country, offset by country, so tier counts differ by at most one per country. Calibration (400) and test (1,000) are not divisible by 3, so tiers there are near-equal rather than exact; dev is exactly equal.
- **The hard set is hand-written.** One YAML file per country, validated (required `TwnNm` and `Ctry`, XSD lengths and patterns, known tags, every gold value found in the raw lines, unique ids), then converted to `hard.jsonl` with the difficulty computed from the tags. Entries marked `example: true` show the format and are left out of `hard.jsonl`. The converter insists on exactly 100 entries unless `--allow-partial`, so a half-written set cannot be mistaken for the finished one. `hard.jsonl` is empty until the owner writes entries.
- **Messages.** Each message carries a debtor and a creditor as unstructured `AdrLine` text, with a bank BIC whose country letters match the address (the Phase 1 country hint). 300 messages, alternating pacs.008 and pain.001, use all 600 dev addresses once. About 30% of jobs get one fault.
- **Faults only move or remove text, so gold never changes.** `missing_country`: country text removed from the end. `town_in_line`: the town (plus anything before it on its line) moved onto the previous line, keeping token order; whole-word match only. `too_many_lines`: the same text cut at spaces into 8 `AdrLine` lines.
- **`too_many_lines` messages fail the XSD on purpose** (`AdrLine` maxOccurs is 7). The manifest records `xsd_valid` per message; the build stops if validity does not match the faults injected. All other messages validate. The fault needs 8 words, so it is rarer than the others.
- **New dependencies:** `lxml` (XSD validation, as requested) and `PyYAML` (hard-set files), both pinned in `data/generator/requirements.txt`.

## Consequences

- Phase 3 and 4 tune on dev and calibration only. Nothing reads `test.jsonl` until the final evaluation.
- Regenerating with the same seed reproduces dev, calibration, test and the messages byte for byte; tests check this.

## Re-freeze of the test split (2026-10-29)

- **What:** the test split was regenerated and `test.sha256` replaced. Old hash `1b5a0da2267ae10a41f4d985a8a8c06e436f8d1f6f8e0c05ddf5fe9ea4c32701`, new hash `6177fd24f554b179f24b5c38ddf99b659649d236b83e3027ff260825ca55e11c`. dev, calibration and the 300 sample messages were regenerated in the same run, so the test split was re-frozen once.
- **Why:** postcode-to-town tie defects were found in the US, IN and DE tables (and a locality-to-outward-code gap in GB) by checking them against GeoNames, before any evaluation use of the test split. Nothing had been tuned on or scored against test. Details: `postcode-ties.md`.
- **Approval:** the project owner approved the re-freeze. `test.jsonl` was not opened or printed; the check that it would change was a hash comparison.
- **Rule from now on:** the test split must not be regenerated again without the owner's explicit approval.
