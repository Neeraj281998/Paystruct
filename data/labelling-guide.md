# Labelling guide

Status: approved, sections 0 to 19. Section 20 (records with no town) awaits approval. Settles every ambiguous case once, so gold labels never contradict each other. The generator, the hand-written hard set and the scorer all follow this file. If a case is not covered, add a rule here before labelling it.

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

**Decision:** decided by the words in the segment. The word lists below are for IE and GB; each new country has its own lists in sections 13-18 (for example "Court" is a street word in the US and a building word here).

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
- Abbreviations are written in the raw text and stay in gold. Tag `abbreviated`. IE and GB: St, Rd, Ave, Dr, Ln, Ter, Cl, Sq, Gdns, Cres, Apt. The other countries use only the abbreviations listed in their own section.
- A raw line over 70 characters is split at a word boundary into the next line, tag `long_line_split`. Gold stays whole, so any value, including a postcode, may end up across two lines. At most 7 raw lines.

## 10. How the scorer compares

A predicted field equals the gold field when, for both: Unicode NFC, case-folded, runs of whitespace collapsed to one space, leading and trailing whitespace and the punctuation `, . ;` trimmed. For `PstCd` only, all whitespace is removed, so "D01K2X7" equals "D01 K2X7". Accents are kept ("Dún" is not "Dun").

Abbreviations: gold keeps the text as written, but a system must not be penalised for either form. So the scorer also treats a value and its allowlisted expansion as equal (IE and GB: St/Street, Rd/Road, Ave/Avenue, Dr/Drive, Ln/Lane, Ter/Terrace, Cl/Close, Sq/Square, Gdns/Gardens, Cres/Crescent, Apt/Apartment; the pairs for the other countries are in sections 13-18). The scorer and the Phase 5 grounding check use one shared allowlist, defined once in Phase 4. Exact match means every gold field matches and no extra field is predicted.

## 11. Difficulty and tags

Difficulty is computed from the tags, so it cannot drift from them.

- **Corruption tags:** `all_caps`, `extra_spaces`, `one_line`, `missing_commas`, `reordered`, `postcode_split`, `postcode_no_space`, `postcode_wrong_line`, `typo`, `abbreviated`, `country_name`, `no_country`, `long_line_split`.
- **hard:** four or more corruption tags, or any of `postal_district`, `no_country`, `postcode_split`, `postcode_wrong_line`, `typo`, `landmark`, `cedex`.
- **medium:** otherwise, two or three corruption tags, or any of `no_street_number`, `flat`, `building_name`, `floor`.
- **easy:** everything else.

Structure tags: `no_street_number`, `postal_district`, `flat`, `building_name`, `floor`, `po_box`, `county` (any `CtrySubDvsn`: a county, state or province), `locality`, `landmark` (India, section 18), `cedex` (France, section 13), `partial_postcode` (a lone routing key or outward code, section 5; hand-written set only), `not_in_geonames` (section 19; hand-written set only, optional), `no_town` (section 20; hand-written set only). None of the last three changes the difficulty tier, and the generator never writes them.

## 12. Rules common to the six new countries

- **Natural order.** Number position: before the street in FR, CA, US, IN; after it in DE, NL. Postcode position: before the town in FR, DE, NL; after the town in CA and US (with the state between) and in IN (state, then PIN). `reordered` means any departure from the country's own natural order.
- **Compound street names (DE, NL).** The street word is the end of the name ("Hauptstraße", "Keizersgracht") or a separate word ("Berliner Straße"). Either way the whole name is `StrtNm`.
- **Region (`CtrySubDvsn`)** is labelled only when written, as written. It is always written in CA, US and IN, never generated in FR, DE and NL.
- **Case and accents.** As in section 0, gold follows the text. In German all-caps text "ß" becomes "SS" ("HAUPTSTRASSE"), and gold follows. Accents are kept (NFC).
- Countries, their words and their abbreviations live in the country's own section. Gold `Ctry` is the ISO code in every case.

## 13. France (FR)

Natural: `12 Rue des Tilleuls` / `69003 Lyon` / `France`.

- `StrtNm` includes the type word, which comes first: "Rue des Tilleuls", "Avenue Victor Hugo". Street words: Rue, Avenue, Boulevard, Place, Chemin, Impasse, Allée, Quai, Route, Cours, Passage, Square.
- `BldgNb` keeps "bis" and "ter" ("12 bis").
- Building words: Résidence, Bâtiment, Immeuble, Tour, Villa. "Résidence Les Tilleuls" is `BldgNm`. "Appartement 12", "Appt 12", "Bureau 4" are `Room`. "3ème étage", "2e étage", "Rez-de-chaussée" are `Flr`. "BP 123" is `PstBx`.
- **Cedex:** the suffix stays with the town: "69003 Lyon Cedex 03" gives `PstCd` "69003", `TwnNm` "Lyon Cedex 03". Tag `cedex`.
- **Arrondissement:** "75008 Paris" gives `TwnNm` "Paris". If written "Paris 8e", `TwnNm` is "Paris 8e" (the district stays with the town, as for Dublin). Tag `postal_district`.
- Country written: "France". Abbreviations: Av./Avenue, Bd/Boulevard, Pl./Place, Ch./Chemin, Imp./Impasse, All./Allée, Appt/Appartement, Bât./Bâtiment.

## 14. Germany (DE)

Natural: `Hauptstraße 12` / `20095 Hamburg` / `Deutschland`.

- Number after the street: `StrtNm` "Hauptstraße", `BldgNb` "12". Letters stay as written ("12a"); ranges stay whole ("12-14").
- Street endings: -straße, -strasse, -str., -weg, -allee, -platz, -gasse, -ring, -damm, -ufer. Names with no such ending ("Am Markt", "An der Mühle") are hand-written set only.
- Building words: Haus, Gebäude, Turm, Center. "Wohnung 5", "Whg. 5", "Zimmer 3", "Büro 12" are `Room`. "3. OG", "EG", "Erdgeschoss", "2. Etage" are `Flr` as written. "Postfach 1234" is `PstBx`. "c/o" is not generated.
- Country written: "Deutschland", "Germany". Abbreviations: Str./Straße and Str./Strasse, also as an ending ("Hauptstr." = "Hauptstraße").

## 15. Netherlands (NL)

Natural: `Keizersgracht 99` / `1015 CJ Amsterdam` / `Nederland`.

- Number after the street, as in Germany. Number additions stay in `BldgNb` in the forms "99A" and "99-2". Other forms ("99 2hg", "99 bis") are hand-written set only.
- Street endings: -straat, -laan, -weg, -gracht, -plein, -kade, -singel, -dijk, -steeg, -hof, -pad.
- `PstCd` is four digits, a space, two letters: "1015 CJ". "1015CJ" is `postcode_no_space`.
- Building words: Gebouw, Toren. "Unit 4", "Kamer 5" are `Room`. "2e etage", "Begane grond" are `Flr`. "Postbus 123" is `PstBx`.
- Country written: "Nederland", "The Netherlands", "Netherlands", "Holland". No abbreviations are generated.

## 16. Canada (CA)

Natural: `123 Main Street` / `Toronto ON M5V 2T6` / `Canada`.

- Province is `CtrySubDvsn` as written, code or name ("ON", "Ontario", "QC", "Québec"). Postal code format A1A 1A1, `PstCd` as written with its space; "K1A0B1" is `postcode_no_space`.
- English and French. French puts the type first and keeps it in `StrtNm` ("rue Sainte-Catherine Ouest", "boulevard René-Lévesque"). Directionals (East, Est, Ouest, E, W, O) stay in `StrtNm`.
- English street words: Street, Avenue, Road, Drive, Crescent, Boulevard, Court, Way, Lane, Trail, Place. French: rue, avenue, boulevard, chemin, rang, place, côte, montée. In CA "Court" is a street word.
- Building words: Building, Tower, Centre, Plaza, Complex; French: Édifice, Tour, Complexe.
- "Unit 5", "Suite 200", "App. 5", "Bureau 200" are `Room`. "3rd Floor", "3e étage" are `Flr`. "PO Box 123", "C.P. 123" are `PstBx`.
- **Unit-number prefix** ("5-123 Main St" = unit 5, number 123): `Room` "5", `BldgNb` "123". Hand-written set only; the generator never writes hyphenated numbers for CA.
- Country written: "Canada". "CA" in the text of a US address is California, a state, never the country. Abbreviations: Blvd/Boulevard, Ct/Court, Pl/Place, Ave/Avenue, St/Street, Rd/Road, Dr/Drive, Ln/Lane, Cres/Crescent, Ste/Suite, N/North, S/South, E/East, W/West.

## 17. United States (US)

Natural: `123 Main St` / `Austin, TX 78701` / `USA`.

- State is `CtrySubDvsn` as written ("TX", "Texas"). `PstCd` is the ZIP or ZIP+4 as written, hyphen kept ("78701-1234").
- Directionals before or after the street stay in `StrtNm` ("N Main St", "Main St NW").
- Street words: Street, St, Avenue, Ave, Boulevard, Blvd, Drive, Dr, Lane, Ln, Road, Rd, Court, Ct, Way, Place, Pl, Parkway, Pkwy, Circle, Cir, Trail, Trl, Highway, Hwy, Terrace. "Court" is a street word here.
- Building words: Building, Tower, Plaza, Center, Complex.
- "Apt 5B", "Suite 200", "Ste 200", "Unit 3", "#5" are `Room` as written (the keyword or "#" stays). "5th Floor", "Fl 5" are `Flr`. "P.O. Box 123" is `PstBx`.
- Country written: "USA", "U.S.A.", "US", "United States", "United States of America". Abbreviations: the CA list, plus Apt/Apartment.

## 18. India (IN)

Natural: `Flat 301, Sunrise Residency` / `Plot 12, MG Road` / `Koregaon Park` / `Pune, Maharashtra 411001` / `India`.

- `PstCd` is the six-digit PIN as written; "411 001" is also written that way.
- State is `CtrySubDvsn` as written. City is `TwnNm`. Area, colony, nagar, sector or layout names are `TwnLctnNm` ("Koregaon Park", "Sector 5", "Andheri East"). A main road is `StrtNm` ("MG Road", "Station Road").
- Plot, house and door numbers go in `BldgNb` **with their keyword**: "Plot 12", "House No. 45", "Door No. 12-3-45" (16 characters or fewer). The keyword stays so the value is text from the line and no keyword is left over. This may disadvantage baselines that output the number alone, so **Phase 4 reports IN separately**. "Flat 301", "Flat No. 301" are `Room`. "3rd Floor" is `Flr`.
- Street words: Road, Rd, Marg, Street, Lane, Cross, Highway. Building words: Residency, Towers, Heights, Apartments (plural), Plaza, Complex, Mansion. "Apartment 5" (singular, with a number) is a `Room`.
- **Landmarks** ("near City Mall", "opp. Railway Station", "behind SBI Bank") are **not labelled**. They are not in gold; the record is tagged `landmark`. A system must not put one into a structured field (in a hybrid address it belongs in `AdrLine`). The scorer ignores unlabelled text. In the generator tests, "every raw token is explained" exempts only the landmark phrase, and only if it is one contiguous span of the raw text; every other token must still be explained.
- Country written: "India". Abbreviations: Rd/Road, Apt/Apartment.

## 19. Postcode-to-town ties (generator and gold)

Added with the GeoNames tie fix (`docs/decisions/postcode-ties.md`). Generated gold never contradicts GeoNames at the granularity in the table below, because the generator only writes a postcode GeoNames lists for the town. This section says how tightly each country's pairing is tied, and what is left random. The hand-written hard set is not bound by it: its entries are checked against real-world knowledge, not against this table.

| Country | Town and postcode are tied at | Source check | Left random (never tied) |
|---|---|---|---|
| US | the full ZIP (a ZIP GeoNames lists under the city and state) | confirmed | ZIP+4 extension |
| DE | the full postcode (listed under the town's own place name) | confirmed | none |
| NL | the four digits, within the town's range | confirmed where listed (515 of 720 numbers; the rest not in the file) | the two letters |
| FR | the full postcode; Paris, Lyon, Marseille also by arrondissement | confirmed | the Cedex number |
| IN | the full PIN of the city; a sector only with its own PIN; a locality with its own PIN where known (36 of 46) | confirmed for city, sector and 26 localities; 10 localities from memory, 10 with no tie | none |
| GB | the outward code (post town and outward code); a locality with an outward code GeoNames lists for it (42 of 72) | 43 of 61 town-code pairs confirmed, 18 not (GeoNames lists localities, not post towns); no contradiction | the inward half; the locality's code for the other 30 |
| IE | the routing key (town and routing key; Dublin district and its key) | 43 of 46 confirmed, 3 not; county and locality ties are not checkable | the unique identifier; which locality |
| CA | the first three characters (city and area code; province always checked) | 44 of 47 confirmed, 3 not | the last three characters |

Rules for labelling:
- A hand-written entry is never dropped or altered because GeoNames lacks its postcode. If its town and postcode pairing is not listed in GeoNames (at the granularity in the table), it may carry the optional tag `not_in_geonames`, so Phase 4 can report those entries separately.
- Gold still keeps the text as written (section 0); the tie says nothing about accents or case.
- The pairings not confirmed by GeoNames are listed in `docs/decisions/postcode-ties.md`: IE (Ennis V95, Navan C15, Killarney V93, all county and all locality-to-key ties), GB (18 post-town codes, 30 localities), CA (Montréal H2X and H4A, Québec G1V), IN (20 localities).
- Because the generator and the rules engine both use GeoNames, town and postcode accuracy on the synthetic splits is optimistic. See `docs/decisions/geonames-circularity.md`; report the hard-set result beside it.

## 20. Records with no town (`no_town`)

Some real addresses arrive with a postcode (or nothing) but no town. Hand-written set only; the generator never writes one. Tag `no_town`.

- **Gold has no `TwnNm`.** Gold may only hold text that is in the raw lines (section 0), and there is no town text. Every other field is labelled as usual, and a postcode that is present stays in `PstCd`.
- **`Ctry` is still the true country.** If the country is not in the text, the record also carries `country_hint` and the tag `no_country` (section 8).
- **Expected system behaviour: output no town and route the record to review.** A system must not derive a town from the postcode, a gazetteer or the country; that would invent a value that is not in the input. Phase 4 reports these records separately, because the right answer is an empty `TwnNm`, not a guess.
- `no_town` is the only case where `TwnNm` may be missing from gold. The hard-set validator requires `TwnNm` in every other record.
