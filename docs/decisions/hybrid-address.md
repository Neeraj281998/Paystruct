# Hybrid address fallback

Date: 2026-10-30. Status: accepted, with an open question.

## Decision

When the rules cannot fully structure an address but a town and a country are known, the engine returns a hybrid address: `TwnNm` and `Ctry` structured, everything else in `AdrLine`, the original text, packed into lines of at most 70 characters (the XSD `Max70Text`). It is a proposal for the router; a hybrid address is never ACCEPT.

## Open question: the real limit

The XSD allows up to 7 `AdrLine` entries (`docs/decisions/xsd-versions.md`), but the maximum that CBPR+ allows in a hybrid address is a usage-guideline rule that has not been confirmed from the guidelines for this project. **The limit must be confirmed against the CBPR+ usage guidelines before anyone relies on it.** Until then `max_adr_lines` in `agent/rules/config.yaml` is a placeholder of 2 (not the XSD's 7), chosen to be the stricter value. If more lines are needed the hybrid is not produced (`hybrid_too_long`) and the address stays NEEDS_LLM or REVIEW.

This project does not claim CBPR+ certification. It implements a documented subset of CBPR+ address rules.

## Consequences

- The limit is one config value, so confirming it is a one-line change plus a test.
- With no town written there is no hybrid (section 20): the address goes to REVIEW.

## Day 4

The agent's validator (`agent/repair/validator.py`, HYBRID_LINES_EXCEEDED and HYBRID_DUPLICATION) reads the same `max_adr_lines` config value. It remains a placeholder: the real CBPR+ limit must be confirmed before anyone relies on it.
