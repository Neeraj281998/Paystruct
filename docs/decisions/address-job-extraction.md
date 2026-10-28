# How address jobs are extracted

Status: accepted (Phase 1)

## Decisions

- **Roles** come from the element that holds the `PstlAdr`: Dbtr, Cdtr, UltmtDbtr, UltmtCdtr, InitgPty, the agent elements (DbtrAgt, CdtrAgt, IntrmyAgt1-3, InstgAgt, InstdAgt, PrvsInstgAgt1-3, FwdgAgt) and `OTHER` for any other party with a `PstlAdr` (invoicer, garnishee). Nothing is silently skipped.
- **Out of scope:** `PstlAdr` under `RmtLctnDtls`, `ChqFr` and `DlvrTo`. Those are `NameAndAddress` blocks (a name plus an `Adr` child), not parties.
- **Agents:** a job is made for every agent with a `PstlAdr`, whether or not it also has a BIC. The spec's "agents without a BIC" is the common case, but an address worth structuring should not be dropped because a BIC sits beside it.
- **Country hint:** characters 5 and 6 of the party's own BIC (`AnyBIC`, or `BICFI` for an agent). If the party has none, the BIC of its bank: DbtrAgt for debtor and ultimate debtor, CdtrAgt for creditor and ultimate creditor, found by walking up from the party to the nearest enclosing element that has one. This is resolved after the pass, because the bank can follow the party in document order. A BIC that fails the XSD pattern gives no hint. It is a hint only.
- **`alreadyStructured`:** no `AdrLine`, and both `TwnNm` and `Ctry` present. A hybrid address (town and country plus `AdrLine`) is not already structured. The XSD itself requires none of these elements; town and country come from the CBPR+ usage-guideline rule.
- **`existing`** is a map keyed by XSD element name in XSD order, so no field list is hard-coded; `AdrTp` is kept as its code or proprietary id.
- **`xmlPath`** uses an index on every step except the root (`.../CdtTrfTxInf[2]/Cdtr[1]/PstlAdr[1]`), so each address is uniquely locatable.

## Differences from the spec's `AddressJob` record

Two components are added: `jobId` (every later write is keyed by job id) and `alreadyStructured` (requested for Phase 1). The seven spec components are unchanged.

## Consequences

- Phase 3 can skip jobs with `alreadyStructured` and validate them only.
- Field names and lengths are read from the XSD (`PostalAddressSchema`), per `xsd-versions.md`.
