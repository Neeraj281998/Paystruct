# Labelling guide

Status: DECISIONS APPLIED, waiting for approval. Settles every ambiguous case once, so gold labels never contradict each other. The generator, the hand-written hard set and the scorer all follow this file. If a case is not covered, add a rule here before labelling it.

Element names and maximum lengths come from the XSD (`docs/decisions/xsd-versions.md`), not from the spec table. Fields used in v1: `StrtNm`, `BldgNb`, `BldgNm`, `Flr`, `Room`, `PstBx`, `PstCd`, `TwnNm`, `TwnLctnNm`, `CtrySubDvsn`, `Ctry`. Not used in v1: `Dept`, `SubDept`, `UnitNb`, `DstrctNm`, `CareOf`.

## 0. Core rule: gold keeps the original text

Every gold value is exactly the text from the raw lines, with its original spelling, casing, abbreviation and punctuation. Nothing is expanded, corrected or recased. This matches the system's guarantee: PayStruct never outputs a value that is not in the input. The only gold value that may be missing from the raw text is the country code (`Ctry`, see section 8).

```
raw:  "14 MAIN ST"   ->  gold: BldgNb "14", StrtNm "MAIN ST"       (St stays St; not "Main Street")
```

A value wrapped across two lines, or a postcode split across two lines, is the same tokens joined with one space. Extra spaces in a raw line appear only between values or at the ends of a line, never inside one value, so gold values have single spaces.

## 1. Dublin postal districts

**Decision:** the district number stays with the town. `TwnNm` = "Dublin 1" (also "Dublin 6W"). `DstrctNm` is never used for it. This follows the spec's own example.

```
"Dublin 1 D01 K2X7 Ireland"  ->  TwnNm "Dublin 1", PstCd "D01 K2X7", Ctry "IE"
```

A named suburb on its own line before the town is `TwnLctnNm`: `"Ranelagh" / "Dublin 6"` -> `TwnLctnNm "Ranelagh"`, `TwnNm "Dublin 6"`.

## 2. Flat, unit, apartment, room: Room or Flr

**Decision:** flat, apartment, unit, suite and room numbers go in `Room`, **keeping the keyword** ("Flat 2", "Unit 4", "Apt 5B"), as in the spec example. `Flr` is only for an explicit floor ("2nd Floor", "Floor 3", "Ground Floor", "Basement").

```
"Flat 2, 3rd Floor, 14 Marlow Court"  ->  Room "Flat 2", Flr "3rd Floor", BldgNb "14", BldgNm "Marlow Court"
```

**`UnitNb` exists** in the pacs.008.001.14 and pain.001.001.13 XSDs (`Max16Text`, between `Flr` and `PstBx`). It is **not used yet**. The project owner will check the CBPR+ usage guidelines before any switch of "Unit 4" from `Room` to `UnitNb`. If that happens, this section and every gold label with a unit change together.

## 3. Building name versus street name

**Decision:** decided by the words in the segment.

- Street words: Street, St, Road, Rd, Lane, Ln, Avenue, Ave, Drive, Dr, Terrace, Ter, Close, Cl, Way, Place, Square, Sq, Quay, Crescent, Cres, Gardens, Gdns, Grove, Row, Hill, Walk. A segment with one is `StrtNm`.
- Building words: House, Court, Lodge, Tower, Building, Centre, Plaza, Mansions, Cottage, Business Park, Industrial Estate, Block. A segment with one (and no street word) is `BldgNm`, even if it could be a street name.
- A "Block B" prefix stays inside the building name; "Unit 4" goes to `Room` (section 2).
- A number directly before a street is `BldgNb`; directly before a building name it is also `BldgNb`. Ranges stay whole ("12-14").
- No number anywhere: tag `no_street_number`, leave `BldgNb` out. (A PO box number is not a street number, section 7.)

```
"Unit 4 Block B Docklands Business Park"  ->  Room "Unit 4", BldgNm "Block B Docklands Business Park"
"12 Orchard Lane"                         ->  BldgNb "12", StrtNm "Orchard Lane"
```

## 4. Irish county

**Decision:** `CtrySubDvsn`, as written including "Co." or "County" ("Co. Cork"). Only labelled when the text has it; never inferred from the town. "Co. Dublin" is a county; "Dublin 1" is a town (section 1).

```
"Galway H91 AB12" + "Co. Galway"  ->  TwnNm "Galway", PstCd "H91 AB12", CtrySubDvsn "Co. Galway"
```

## 5. Eircode routing key

**Decision:** `PstCd` holds the whole Eircode as written: routing key plus unique identifier ("D01 K2X7"; "D01K2X7" if written without the space). The routing key is never a separate field. A lone routing key or a UK outward code with no second half is kept as `PstCd` as written, tagged `partial_postcode` (hand-written set only, the generator does not make these). A routing key is not a town: "D01" never becomes `TwnNm`.

## 6. UK building names and flats

**Decision:** same rules as sections 2 and 3, plus: the post town (the line with the postcode) is `TwnNm`; a locality line above it is `TwnLctnNm`; a county is `CtrySubDvsn` only when written; "England", "Scotland", "Wales" or "Northern Ireland" written as the last line is `CtrySubDvsn`, and `Ctry` is still "GB" (so with no other country text the record is `no_country`).

```
"Flat 2, Marlow Court, 14 Riverside Road, BRISTOL BS1 4XY"
   ->  Room "Flat 2", BldgNm "Marlow Court", BldgNb "14", StrtNm "Riverside Road", TwnNm "BRISTOL", PstCd "BS1 4XY", Ctry "GB"
"Rose Cottage, High Street"  ->  BldgNm "Rose Cottage", StrtNm "High Street"      (no number: no_street_number)
```

## 7. PO boxes

**Decision:** `PstBx`, keeping the keyword and the written form ("PO Box 123", "P.O. Box 123"), always 16 characters or fewer. A PO box address has no `StrtNm`; town and postcode still apply.

```
"PO Box 1234" / "Cork T12 XY34"  ->  PstBx "PO Box 1234", TwnNm "Cork", PstCd "T12 XY34"
```

## 8. Country

`Ctry` is always the uppercase ISO code: IE for Ireland, Eire, Republic of Ireland; GB for UK, United Kingdom, Great Britain. If the text has no country, `Ctry` is still the true country, the record carries `country_hint` set to it, and the tag `no_country` is added. This is the only case where gold holds a value that is not in the raw text. A country written as a name or "UK" is tagged `country_name`; written as the ISO code ("IE", "GB") it has no tag.

## 9. Typos, abbreviations and long lines

- Typos are made only in `StrtNm` and `BldgNm` (a word of the name, not the street or building word, and not the first letter). Never in towns, postcodes, numbers or countries. Gold keeps the typo as written, because PayStruct must never output a value that is not in the input. Records with a typo are tagged `typo` so results can be broken out separately.
- Abbreviations (St, Rd, Ave, Dr, Ln, Ter, Cl, Sq, Gdns, Cres, Apt) are written in the raw text and stay in gold. Tag `abbreviated`.
- A raw line over 70 characters is split at a word boundary into the next line, tag `long_line_split`. Gold stays whole, so any value, including a postcode, may end up across two lines. At most 7 raw lines.

## 10. How the scorer compares

A predicted field equals the gold field when, for both: Unicode NFC, case-folded, runs of whitespace collapsed to one space, leading and trailing whitespace and the punctuation `, . ;` trimmed. For `PstCd` only, all whitespace is removed, so "D01K2X7" equals "D01 K2X7". Accents are kept ("Dún" is not "Dun").

Abbreviations: gold keeps the text as written, but a system must not be penalised for either form. So the scorer also treats a value and its allowlisted expansion as equal (St/Street, Rd/Road, Ave/Avenue, Dr/Drive, Ln/Lane, Ter/Terrace, Cl/Close, Sq/Square, Gdns/Gardens, Cres/Crescent, Apt/Apartment). The scorer and the Phase 5 grounding check use one shared allowlist, defined once in Phase 4. Exact match means every gold field matches and no extra field is predicted.

## 11. Difficulty and tags

Difficulty is computed from the tags, so it cannot drift from them.

- **Corruption tags:** `all_caps`, `extra_spaces`, `one_line`, `missing_commas`, `reordered`, `postcode_split`, `postcode_no_space`, `postcode_wrong_line`, `typo`, `abbreviated`, `country_name`, `no_country`, `long_line_split`.
- **hard:** four or more corruption tags, or any of `postal_district`, `no_country`, `postcode_split`, `postcode_wrong_line`, `typo`.
- **medium:** otherwise, two or three corruption tags, or any of `no_street_number`, `flat`, `building_name`, `floor`.
- **easy:** everything else.

Structure tags: `no_street_number`, `postal_district`, `flat`, `building_name`, `floor`, `po_box`, `county` (any `CtrySubDvsn`), `locality`.
