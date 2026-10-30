# Python rules engine (Day 2)

Date: 2026-10-30. Status: accepted. Code: `agent/rules/`. Tests: `agent/tests/`.

## What it is

A chain of small rules over a `ParseState`. Each rule is a class with `apply(state) -> state` (the input state is never changed) and its own unit tests. The order is `order:` in `agent/rules/config.yaml`: normalise, country, postcode, region, pobox, floor, unit, town, landmark, street, locality, length, confidence, routing, hybrid. The engine is the `parse_address` tool and the rules-only baseline of the later days. No LLM code is here.

`ParseState` holds the tokens (with character offsets into the NFC-joined raw lines), the fields found, the evidence for each (rule id and why), a confidence per field, the character spans per field, the leftover text, flags, the route and the optional hybrid address.

## Main choices

1. **Python only, no second validator.** The Java service stays the ingestion front door. Element names and maximum lengths are read from the supplied XSD at startup (`agent/rules/xsd.py`, `PostalAddress27`), not hard-coded. A test checks that the pacs.008 and pain.001 definitions agree.
2. **Country profiles are data.** One YAML per country in `agent/rules/countries/` (postcode regexes, number position, street, building, unit, floor and PO box words, regions, town suffixes, landmark words, country names). A test adds a ninth country by writing a file and changing no Python. The profiles follow labelling-guide sections 12 to 18 and were not derived from the generator.
3. **Never derive a value that is not in the input.** Every output value, except `Ctry`, is cut from the text (a Hypothesis test checks this). The gazetteer checks a town that is written; it never supplies one. If no town is written, `TwnNm` stays unset and the route is REVIEW (guide section 20). `Ctry` may come from a hint or from cues when the text names no country; its evidence says so and its confidence is lower.
4. **Country detection order:** ISO code at the end of a segment, then a country name, then a postcode pattern unique to one country, then region names, then street and gazetteer cues, then the hint. Strong evidence that disagrees (for example the name "Ireland" with a UK postcode) is a contradiction and routes to REVIEW. "CA" before a US ZIP is California; "Fort Wayne, IN" is Indiana, decided by the US gazetteer. "Northern Ireland" is not Ireland. A street such as "Rue Anatole France" does not make France.
5. **Town search is near the postcode first.** Candidates are gazetteer matches that are not street or building words, scored by closeness to the postcode and region, then population. Written arrondissements, Dublin districts and Cedex suffixes stay with the town. A written town the gazetteer lacks is kept at low confidence and routes to NEEDS_LLM.
6. **Landmarks stay unlabelled** (guide section 18) and are reported as leftovers. If a landmark runs to the end of the text with no separator, where it stops is a guess, so the address is not accepted.
7. **Lengths:** a value over its XSD maximum is dropped, never truncated, and the address routes to NEEDS_LLM.
8. **Hybrid fallback:** when the address is not fully structured but a town and country exist, `hybrid` holds `TwnNm`, `Ctry` and the rest in `AdrLine`, packed into lines of at most 70 characters and at most `max_adr_lines`. See `hybrid-address.md`.
9. **Allowlist and scorer.** `agent/rules/allowlist.py` is dependency-free (a test enforces it) and holds the abbreviation pairs of guide sections 10 and 13 to 18 per country. `agent/rules/scoring.py` implements section 10: NFC, case-folded, whitespace collapsed, `, . ;` trimmed, `PstCd` without whitespace, allowlisted pairs equal; exact match needs every gold field and no extra field. The Day 4 grounding check imports the same allowlist.
10. **Confidence and routing** use simple signals (a rule set the field, gazetteer agreement, no unclaimed text, hint agreement). Two agreeing signals combine as 1 - (1-a)(1-b). **The thresholds in `config.yaml` are placeholders**; they are set on the calibration split on Day 5. Routes: ACCEPT, NEEDS_LLM (unclaimed text, a dropped value, a partial postcode, an unverified town, an unbounded landmark, or low confidence) and REVIEW (contradiction, no country, no town written, or very low confidence). Leftover text is always reported.
11. **The CLI refuses** any split but `dev` and `calibration`, loudly and with exit code 2; its source never names the test or hard files.

## Circularity caveat

Dev accuracy is optimistic. The generator and the gazetteer both use GeoNames, so a town or postcode the generator writes is one the gazetteer knows. The generator is also a small set of templates, and the engine was tuned on dev only until it stopped finding failures there. A result on dev (or on calibration) says the engine follows the labelling guide on generator-shaped text; it does not say how it will do on real addresses. The AI-drafted, AI-verified hard set is the independent check, and its results must be reported beside the synthetic ones. No accuracy number is quoted here: numbers come from `eval_runs` records, which the Day 3 harness creates.

## Remaining failure patterns (found by stressing dev text, not by reading the hard set)

- **No separators.** When commas and line breaks are removed, a locality has nothing to mark where it starts, so it is absorbed into a building name, a landmark or a street, and the address can be accepted wrongly. This is the biggest remaining source of false accepts.
- **Building name next to a street with no number** in countries where the building word is not a prefix (GB, IE, IN, US), and German or Dutch building names with no particle between name and street.
- **Reordered lines** that put a postcode half on a different line from its other half, or a number far from its street.
- **Locality versus town.** Both can be in the gazetteer; the nearer-to-postcode, larger-population choice is a heuristic and fails when a large suburb sits next to a small town.
- **Towns the gazetteer lacks** (cities500 stops at 500 inhabitants) are kept only when written right beside the postcode or region, at low confidence.
- **Region that is also a town** (Delhi, Chandigarh, Washington, New York) is decided by whether another town is written.
- **Regions of GB** use a fixed list of nations and counties; unlisted counties are left as unclaimed text.
- **Hard-set style cases** that the guide settles by rule (care-of lines, rural routes, stations, talukas, renumbered doors) are not yet recognised; they fall out as unclaimed text and route to NEEDS_LLM, which is the safe failure.
- **Hinglish landmarks** are recognised only by the "ke paas" ending.

## Not done on purpose

No LLM, agent, MCP, Kafka, calibration of thresholds, or use of the test and hard splits.
