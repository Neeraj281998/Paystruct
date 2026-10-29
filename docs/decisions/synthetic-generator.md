# Synthetic address generator

Status: accepted (Phase 2A)

## Decisions

- **Reverse generation.** The ground truth (parts with field names) is built first and rendered second, so gold is known before the mess is made. Gold keeps each value exactly as written in the raw text (labelling guide section 0), because PayStruct must never output a value that is not in the input. The only gold value allowed to be absent from the raw text is `Ctry`. Tests check that every other gold value appears in the raw text exactly as written, and that every raw token is either part of a gold value or the country.
- **Difficulty is computed from the tags**, not assigned. The generator picks a target tier, samples structure and corruptions suited to it, then keeps the attempt only if the computed tier equals the target (rejection sampling). So tiers cannot drift from the guide, and tiers stay balanced.
- **A corruption is tagged only if it changed something.** Each corruption function reports whether it had an effect (for example `missing_commas` is not tagged when there was no comma to leave out).
- **Typos only in street and building names** (not the street or building word, not the first letter), at a controlled rate: a share of hard records, decided before sampling so the rate holds. Gold keeps the typo.
- **One random generator per record**, seeded from `(seed, country, index, tier)`. A record does not depend on how many records were requested, which lets Phase 2B draw disjoint index ranges for different splits. Tests run the command line under different `PYTHONHASHSEED` values to prove no set ordering leaks into the output.
- **Limits come from the XSD**, read by `addrgen/limits.py`, and a test compares them with the table in `docs/decisions/xsd-versions.md`.
- **Faker is used for surnames only** (in street and building names, with the `en_IE` and `en_GB` locales). Towns, counties, routing keys and outward codes come from small curated tables, because Faker's cities are not real places. Faker is pinned in `requirements.txt` because its output can change between versions.
- **One module per country**, discovered by importing the `countries` package. The country supplies its data, a town block and a postcode split; templates, corruptions, tags and validation are shared.

## Phase 2B: the six further countries

- **Hooks, not branches.** Number position, where a flat or unit line goes, whether the street word comes first, abbreviation tables, where a typo may go, and every format check are methods or attributes on the country module with IE/GB defaults. Corruptions and the renderer call the module, so no country is special-cased in shared code.
- **Unlabelled text.** A `Part` with no field is written but never in gold. It exists for Indian landmarks (guide section 18). The raw-token test exempts only that phrase, and only if it is one contiguous span.
- **Commas inside a line.** `Part.comma_after` writes "Austin, TX 78701" and is dropped by `missing_commas`. A copy bug that lost it for US, CA and IN was caught by a test.
- **Localities are tied to their town** for IE, GB and IN (tables in each module, tested against every generated record). FR, DE, NL, CA and US write no locality.
- **Tags follow the final lines.** `extra_spaces` is decided after line wrapping, because wrapping strips the spaces at a break.
- **Canadian French** towns (Montréal, Québec) get extra weight so about a quarter of CA addresses are in French.

## Python version

Python 3.12 (tested on 3.12.16 with the pinned `requirements.txt`).
