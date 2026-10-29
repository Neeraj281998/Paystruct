# Synthetic address generator

Builds the correct structured address first (the ground truth), then renders it into messy free text, so every record is labelled automatically. All data is synthetic. Every labelling decision is in `../labelling-guide.md`.

Countries: IE, GB, FR, DE, NL, CA, US, IN. Adding a country is adding one module in `addrgen/countries/` that supplies its data and overrides only the hooks where its conventions differ (see `ie.py` for the plain case, `de.py` or `in_.py` for the unusual ones). `tests/test_countries.py` registers a throwaway country to prove it, and each country has its own `tests/test_country_*.py`.

## Setup

```bash
cd data/generator
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Tested on Python 3.12.

## Generate

The project seed is in `SEED`. The same seed and arguments always give byte-identical output.

```bash
.venv/bin/python -m addrgen --seed "$(cat SEED)" --count 300 --countries IE,GB --out /tmp/sample.jsonl
```

Options: `--difficulties easy,medium,hard`, `--start-index N` (first record number per country), `--typo-rate 0.25` (share of hard records that get a typo).

## Test

```bash
.venv/bin/python -m pytest
```

## Splits, hard set, messages

Run from the repository root (`PY=data/generator/.venv/bin/python`):

```bash
$PY scripts/build_splits.py          # dev 600, calibration 400, test 1000 (test is never rewritten once frozen)
$PY scripts/check_splits.py          # no address or id in two splits
$PY scripts/verify_frozen.py         # fails if test.jsonl changed
$PY scripts/split_stats.py dev calibration   # counts by country, difficulty, tag
$PY scripts/validate_hard_set.py     # data/hard_set/*.yaml, format in data/hard_set/README.md
$PY scripts/build_hard_set.py --allow-partial   # data/splits/hard.jsonl
$PY scripts/build_messages.py        # 300 messages from dev into data/messages/ with manifest.json
```

Decisions: `docs/decisions/splits-and-messages.md`.

`scripts/audit_postcode_ties.py` checks the postcode-to-town tables against the GeoNames files, and `scripts/build_postcode_ties.py` rebuilds `addrgen/data/postcode_ties.json` from them (the GeoNames files go in `data/reference/geonames-postal/`, which git ignores). `build_splits.py --refreeze` replaces the frozen test split and needs the project owner's approval.

Postcode and town data: GeoNames postal code data, CC BY 4.0, https://www.geonames.org (GB: includes Royal Mail data, see the GeoNames readme).

## Record format

One JSON object per line: `id`, `country`, `difficulty`, `tags`, `raw_lines`, `gold`, and `country_hint` only when the country is absent from the text. Gold element names and maximum lengths come from the XSD (`addrgen/limits.py` reads `service/src/main/resources/xsd/pacs.008.001.14.xsd`), not from the spec table.
