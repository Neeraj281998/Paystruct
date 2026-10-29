# Postcode-to-town ties

Status: accepted (Phase 2B, 2026-10-29)

## Why

The first generator tables tied US, DE and IN towns to three-digit postcode prefixes with random last digits, written from memory. Checked against GeoNames (`scripts/audit_postcode_ties.py`), many pairings were wrong: Philadelphia 190xx is Abington and Ambler (19085 is Villanova), Seattle 980xx is Auburn (98051 is Ravensdale), Bonn 533xx is Bornheim, Noida 201xxx is mostly Ghaziabad, and so on. 13 of 41 US pairings were contradicted outright, and only 39% of the US ZIPs the generator could write were confirmed. These defects were found before any evaluation use of the test split, so the splits were regenerated and the test split re-frozen (see `splits-and-messages.md`).

## Decisions

- **GeoNames is the source, memory is the exception.** `scripts/build_postcode_ties.py` derives `data/generator/addrgen/data/postcode_ties.json` from the GeoNames postal code files in `data/reference/geonames-postal/` (not committed, ignored by git). The JSON is committed. GeoNames postal code data is licensed CC BY 4.0 (credit: https://www.geonames.org; GB data includes Royal Mail data, see the GeoNames readme).
- **US:** the ZIPs GeoNames lists under the city's place name and state. **DE:** the postcodes GeoNames lists under the town's own place name (the corporate postcodes it also lists under company names are left out). **IN:** the PINs GeoNames lists for the city (same state; place or locality name matching the city or its alias, such as Gurgaon) that start with the city's three-digit prefix, which drops villages of the wider district. All three are 100% confirmed by the audit.
- **IN localities and sectors:** a sector is written only with the PIN GeoNames gives for it (Chandigarh 25 sectors, Noida 13, Gurugram 4). GeoNames disagrees with memory on some of them (it lists Chandigarh sectors 34 and 35 under 160022), so the file wins. A locality is written with its own PIN where GeoNames has a place of that name in the city (26 localities, for example Dwarka with 110075 or 110078). Where GeoNames has none but a remembered PIN is one GeoNames lists for the city, that PIN is used and flagged below (10 localities). Otherwise the locality gets any PIN of the city and is flagged (10).
- **GB:** a locality is written with an outward code GeoNames lists for it, among the codes of the town's own postcode area (42 of 72 localities). The other 30 get one of the post town's codes and are flagged.
- **NL:** Amsterdam's range ends at 1098, because GeoNames lists 1099 under Amsterdam-Duivendrecht.
- **FR, IE, CA unchanged.** FR is 100% confirmed. IE (routing keys), GB (outward codes) and CA (first three characters) are checked at that level, since their GeoNames files hold only the first part of each code.

## Granularity of each country's pairing

See labelling guide section 19. In short: US, DE, IN and FR are tied at the full postcode (IN also at locality and sector where known; FR also at arrondissement); NL at the four digits; GB at outward code (and for localities at the locality's outward code); IE at routing key; CA at the first three characters. Always random, so never tied: US ZIP+4 extension, NL letters, GB inward half, Eircode unique identifier, CA last three characters.

## Pairings GeoNames does not confirm

Audit result after the change: US, IN, DE, FR and NL have no contradicted pairing. The pairings below are kept but not confirmed by GeoNames.

**IE (3 town-to-key entries).** GeoNames lists one place per routing key, and for these keys it names a different town. The keys cover several towns and from memory our three are right:
- Ennis V95 (file says Miltown Malbay), Navan C15 (file says Trim), Killarney V93 (file says Kenmare).
- **IE county ties are all unconfirmed**, because the IE file has no county: Cork (Cork); Galway (Galway); Limerick (Limerick); Waterford (Waterford); Kilkenny (Kilkenny); Sligo (Sligo); Athlone (Westmeath); Drogheda (Louth); Dundalk (Louth); Letterkenny (Donegal); Tralee (Kerry); Ennis (Clare); Wexford (Wexford); Navan (Meath); Carlow (Carlow); Naas (Kildare); Killarney (Kerry); Mullingar (Westmeath); Cavan (Cavan); Castlebar (Mayo); Dún Laoghaire (Dublin); Bray (Wicklow); Swords (Dublin); Tullamore (Offaly).
- **IE locality-to-routing-key pairings are all unconfirmed.** A locality is written beside its town and the town's routing key; GeoNames has no locality data for Ireland:
  - Cork (T12): Douglas, Mahon, Blackrock, Ballincollig, Glanmire, Bishopstown, Wilton, Togher, Montenotte
  - Galway (H91): Salthill, Knocknacarra, Renmore, Oranmore, Claregalway, Ballybrit, Mervue, Doughiska
  - Limerick (V94): Castletroy, Raheen, Dooradoyle, Annacotty, Caherdavin, Corbally
  - Waterford (X91): Tramore, Ferrybank, Ballybeg, Lisduggan
  - Sligo (F91): Strandhill, Rosses Point
  - Athlone (N37): Monksland, Coosan
  - Drogheda (A92): Mornington, Termonfeckin
  - Dundalk (A91): Blackrock, Castletown, Haggardstown
  - Letterkenny (F92): Ballyraine
  - Tralee (V92): Ballymullen, Blennerville
  - Navan (C15): Athlumney, Kentstown
  - Carlow (R93): Graiguecullen
  - Naas (W91): Sallins, Johnstown
  - Killarney (V93): Muckross, Fossa
  - Dún Laoghaire (A96): Glasthule, Monkstown, Sandycove
  - Bray (A98): Ballywaltrim, Little Bray
  - Swords (K67): Applewood, Seatown
  - Towns with no locality: Kilkenny, Ennis, Wexford, Mullingar, Cavan, Castlebar, Tullamore.

**GB (18 post-town-to-outward-code entries).** The county and country are right, but GeoNames lists localities rather than post towns, so the post town is not listed at the code: Bristol BS8, Canterbury CT2, Oxford OX2 and OX4, Cambridge CB1, CB2 and CB4, Manchester M13, Birmingham B15, London SW1A, N1 and NW1, Norwich NR1, Exeter EX1 and EX4, Brighton BN1, Newcastle upon Tyne NE2, Swansea SA2.
- **GB, 30 localities without an outward-code tie** (GeoNames has no place of that name in the town's area): Bedminster, Bristol; Southville, Bristol; Henleaze, Bristol; Widcombe, Bath; Larkhall, Bath; Wincheap, Canterbury; Jericho, Oxford; Newnham, Cambridge; Headingley, Leeds; Armley, Leeds; Chorlton, Manchester; Ancoats, Manchester; Thorpe Hamlet, Norwich; Heworth, York; Acomb, York; Heavitree, Exeter; St Thomas, Exeter; Pennsylvania, Exeter; Kemptown, Brighton; Preston Park, Brighton; Hanover, Brighton; Roath, Cardiff; Cathays, Cardiff; Canton, Cardiff; Uplands, Swansea; Mumbles, Swansea; Stockbridge, Edinburgh; Govanhill, Glasgow; Hillhead, Glasgow; Cults, Aberdeen.

**CA (3 city-to-area-code entries).** GeoNames names neighbourhoods inside the city: Montréal H2X (Plateau Mont-Royal), Montréal H4A (Notre-Dame-de-Grâce), Québec G1V (Sainte-Foy). The provinces of all 47 entries are confirmed.

**IN (20 localities).**
- PIN from memory, kept because GeoNames lists it for the city but has no place of that name: Koregaon Park, Pune: 411001; Hinjewadi, Pune: 411057; T. Nagar, Chennai: 600017; Velachery, Chennai: 600042; Navrangpura, Ahmedabad: 380009; Satellite, Ahmedabad: 380015; Vastrapur, Ahmedabad: 380015; C-Scheme, Jaipur: 302001; Gomti Nagar, Lucknow: 226010; Hazratganj, Lucknow: 226001.
- No PIN tie (any PIN of the city is written): Powai, Mumbai; Borivali West, Mumbai; Banjara Hills, Hyderabad; Jubilee Hills, Hyderabad; Madhapur, Hyderabad; Gachibowli, Hyderabad; Salt Lake, Kolkata; New Town, Kolkata; Maninagar, Ahmedabad; Sushant Lok, Gurugram.

**NL.** The four-digit ranges are confirmed where GeoNames lists a code (515 of 720 codes). The other 205 numbers in the ranges are not in the file; they may be unassigned.

## Consequences

- Accuracy of town and postcode on the synthetic splits is partly a product of using GeoNames (see `geonames-circularity.md`).
- Changing a table changes records; because each record's random generator is seeded by (seed, country, index, tier), only the countries whose tables changed (US, IN, DE, GB, NL) differ, and any change after a freeze needs the owner's approval.
