# Synthetic address generator

Builds the correct structured address first (the ground truth), then renders it into messy free text, so every record is labelled automatically. All data is synthetic. Every labelling decision is in `../labelling-guide.md`.

Countries so far: IE, GB. Adding a country is adding one module in `addrgen/countries/` (see `ie.py`, `gb.py`, and `tests/test_countries.py`, which registers a throwaway country to prove it).

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

## Record format

One JSON object per line: `id`, `country`, `difficulty`, `tags`, `raw_lines`, `gold`, and `country_hint` only when the country is absent from the text. Gold element names and maximum lengths come from the XSD (`addrgen/limits.py` reads `service/src/main/resources/xsd/pacs.008.001.14.xsd`), not from the spec table.
