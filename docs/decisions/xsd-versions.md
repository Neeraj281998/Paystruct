# XSD versions and the postal address type

Status: accepted (Phase 1)

## Context

`docs/spec.md` describes the address elements for `PostalAddress24`. The XSDs supplied for this project are:

- `service/src/main/resources/xsd/pacs.008.001.14.xsd`
- `service/src/main/resources/xsd/pain.001.001.13.xsd`

Both use the type `PostalAddress27` for `PstlAdr`. The definition is byte-for-byte identical in the two files. `PostalAddress27` is used by `PartyIdentification272` (Dbtr, Cdtr, UltmtDbtr, UltmtCdtr, InitgPty, Invcr, Invcee, Grnshee, GrnshmtAdmstr), by `FinancialInstitutionIdentification23` and `BranchData5` (all agents), and, in pain.001 and pacs.008, by `NameAndAddress18` (cheque and remittance-location addresses, which use an `Adr` child and are out of scope).

## Elements of `PostalAddress27`, in XSD sequence order

Every element is `minOccurs="0"`: the XSD requires none of them. Every text type has `minLength` 1, so an empty element is a schema error.

| Element | XSD type | Max length | Occurs | Spec table (PostalAddress24) | Difference |
|---|---|---|---|---|---|
| `AdrTp` | `AddressType3Choice` (`Cd` or `Prtry`) | n/a | 0..1 | not listed | New element |
| `CareOf` | `Max140Text` | 140 | 0..1 | not listed | New element |
| `Dept` | `Max70Text` | 70 | 0..1 | 70 | Same |
| `SubDept` | `Max70Text` | 70 | 0..1 | 70 | Same |
| `StrtNm` | `Max140Text` | 140 | 0..1 | 70 | Spec too small |
| `BldgNb` | `Max16Text` | 16 | 0..1 | 16 | Same |
| `BldgNm` | `Max140Text` | 140 | 0..1 | 35 | Spec too small |
| `Flr` | `Max70Text` | 70 | 0..1 | 70 | Same |
| `UnitNb` | `Max16Text` | 16 | 0..1 | not listed | New element |
| `PstBx` | `Max16Text` | 16 | 0..1 | 16 | Same |
| `Room` | `Max70Text` | 70 | 0..1 | 70 | Same |
| `PstCd` | `Max16Text` | 16 | 0..1 | 16 | Same |
| `TwnNm` | `Max140Text` | 140 | 0..1 | 35 | Spec too small |
| `TwnLctnNm` | `Max140Text` | 140 | 0..1 | 35 | Spec too small |
| `DstrctNm` | `Max140Text` | 140 | 0..1 | 35 | Spec too small |
| `CtrySubDvsn` | `Max35Text` | 35 | 0..1 | 35 | Same |
| `Ctry` | `CountryCode` (pattern `[A-Z]{2,2}`) | 2 | 0..1 | 2 | Same |
| `AdrLine` | `Max70Text` | 70 each | 0..7 | 70 each | The XSD caps the number of lines at 7; the spec gives no count |

Other differences from the spec text:

- The spec table groups `Flr, Room`; in the XSD they are separate elements and `Room` comes after `PstBx`, not next to `Flr`. Element order matters for schema validity.
- "Town and country mandatory" is a CBPR+ usage-guideline rule (spec validation layer 2), not an XSD rule. The XSD accepts an address with neither.
- The XSD gives no limit on how many `AdrLine` entries a hybrid address may use beyond the 7 allowed; the hybrid limit still has to come from the CBPR+ usage guidelines (Phase 3).
- BIC elements: `FinancialInstitutionIdentification23/BICFI` for agents and `OrganisationIdentification39/AnyBIC` (under `Party/Id/OrgId`) for parties. Both match `[A-Z0-9]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?`, so characters 5 and 6 are the country code.

## Decision

From now on the XSD is the source of truth for element names, order, cardinality and maximum lengths. The service reads them from the XSD at startup (`PostalAddressSchema`) instead of hard-coding the spec table. `docs/spec.md` is left as the original conversion of the PDF, and this record lists where it is wrong for the supplied XSDs. Lengths and element names in later phases (rules enforcement, hybrid fallback, LLM schema check) must come from `PostalAddressSchema`, not from the spec table.

## Consequences

- Rules that enforce limits (Phase 3) use 140 for `StrtNm`, `BldgNm`, `TwnNm`, `TwnLctnNm` and `DstrctNm`.
- `CareOf` and `UnitNb` are available as target fields for the rules engine and the LLM output schema.
- A version change (for example a later pacs.008) means adding the XSD and a config entry, then re-checking this table.
