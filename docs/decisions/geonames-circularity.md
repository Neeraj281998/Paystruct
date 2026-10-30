# GeoNames is on both sides of the evaluation (circularity)

Status: accepted (Phase 2B, 2026-10-29)

## The problem

The generator draws towns and postcodes from GeoNames (see `postcode-ties.md`). The Phase 3 rules engine will use GeoNames as its gazetteer (CLAUDE.md: "Gazetteer: GeoNames city data") to recognise towns and check postcodes. So the same source writes the answers and helps find them. On the synthetic splits, accuracy on `TwnNm` and `PstCd`, and any town-postcode consistency check, will look better than it would on independent data, because every town and postcode in the test addresses is, by construction, one the gazetteer knows and ties together correctly. A gain from a larger or better-matched gazetteer is partly the generator's own habits being learned back.

The same applies to anything else the generator and the rules share (street words, abbreviations, the labelling guide's word lists), which Phase 2A already noted; GeoNames makes it stronger for towns and postcodes.

## Decisions

- **The AI-drafted, AI-verified hard set is the independent check.** Its 40 addresses were drafted with AI assistance outside the generator and without GeoNames, then checked by the AI against public sources (not by the project owner), so a result there is not inflated by shared data. Results on it are always reported separately from the synthetic splits (spec: "always report its results separately").
- **This must be reported as a limitation.** Wherever town or postcode accuracy on the synthetic splits is reported (README results table, final write-up, talking points), the text says that the generator and the rules engine share GeoNames, that these numbers are optimistic for that reason, and points to the hard-set number as the unbiased one. Say "synthetic data" every time, as the spec already requires.
- **Baselines are not affected in the same way.** libpostal and Swift's open-source model do not use GeoNames; their numbers on town and postcode fields are therefore a fair reference, and the gap between them and PayStruct on the synthetic splits should not be read as all due to the rules.
- **Do not tune on the overlap.** Phase 3 should not add gazetteer entries or postcode rules by inspecting what the generator produces; the gazetteer is loaded from GeoNames as is.

## Consequences

- Phase 4 reports town and postcode metrics for the synthetic splits and the hard set side by side.
- If the hard set shows a much lower town or postcode score than the synthetic splits, the difference is the size of this effect and goes in the write-up.
