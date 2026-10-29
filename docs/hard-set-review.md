# Hard-set review checklist

Every drafted entry in `data/hard_set/*.yaml` that carries a `# VERIFY` or `# GUIDE?` comment. The entries are AI drafts; each file keeps its 'Drafted by AI' header until you say it is reviewed. Write your decision on the blank line, then edit the YAML entry (and delete its comment) to match.

- 8 VERIFY entries: a postcode may not belong to its town (check against a real source).
- 28 GUIDE? entries: the labelling guide does not decide the case.

## VERIFY: does the postcode belong to the town?

### `ie-h010`

Raw lines:
```
Kilrush, Co. Clare V15 H2R4, 7 Seafield Lane
```
Gold (tags: county, no_country, one_line, reordered):
```
TwnNm: Kilrush
CtrySubDvsn: Co. Clare
PstCd: V15 H2R4
BldgNb: 7
StrtNm: Seafield Lane
Ctry: IE
country_hint: IE
```
Question: Kilrush routing key V15 (believed correct).

- [ ] Resolved
- My decision: 

### `fr-h002`

Raw lines:
```
BP 4021
69256 LYON CEDEX 09
```
Gold (tags: cedex, no_country, po_box):
```
PstBx: BP 4021
PstCd: 69256
TwnNm: LYON CEDEX 09
Ctry: FR
country_hint: FR
```
Question: Is 69256 the Cedex code of Lyon Cedex 09? (believed so)

- [ ] Resolved
- My decision: 

### `de-h002`

Raw lines:
```
Postfach 101112
70049 Stuttgart
```
Gold (tags: no_country, not_in_geonames, po_box):
```
PstBx: Postfach 101112
PstCd: 70049
TwnNm: Stuttgart
Ctry: DE
country_hint: DE
```
Question: Is 70049 the Stuttgart Postfach postcode? PO box postcodes differ from street postcodes, and GeoNames may not list it.

- [ ] Resolved
- My decision: 

### `nl-h002`

Raw lines:
```
Postbus 8423
3503 RK Utrecht
```
Gold (tags: no_country, po_box):
```
PstBx: Postbus 8423
PstCd: 3503 RK
TwnNm: Utrecht
Ctry: NL
country_hint: NL
```
Question: Postbus postcodes for Utrecht are in the 3500-3509 range; is 3503 right?

- [ ] Resolved
- My decision: 

### `us-h004`

Raw lines:
```
P.O. Box 8841
Boise, Idaho 83707
```
Gold (tags: county, no_country, po_box):
```
PstBx: P.O. Box 8841
TwnNm: Boise
CtrySubDvsn: Idaho
PstCd: 83707
Ctry: US
country_hint: US
```
Question: Is 83707 a Boise PO box ZIP? (Boise ZIPs run 83701-83799; not sure of this one)

- [ ] Resolved
- My decision: 

### `us-h006`

Raw lines:
```
94-1021 Hokua Street
Waipahu, HI 96797
```
Gold (tags: county, no_country):
```
BldgNb: 94-1021
StrtNm: Hokua Street
TwnNm: Waipahu
CtrySubDvsn: HI
PstCd: 96797
Ctry: US
country_hint: US
```
Question: Is 96797 the Waipahu ZIP (Hawaii '94-' addresses)? (believed correct)

- [ ] Resolved
- My decision: 

### `us-h008` (also listed under GUIDE? / VERIFY)

Raw lines:
```
RR 2 Box 14
Bethel, VT 05032
```
Gold (tags: county, no_country, po_box):
```
PstBx: RR 2 Box 14
TwnNm: Bethel
CtrySubDvsn: VT
PstCd: 05032
Ctry: US
country_hint: US
```
Question: Is 05032 the Bethel, VT ZIP? (believed correct)

- [ ] Resolved
- My decision: 

### `in-h011`

Raw lines:
```
Door No. 12/345A, Pallimukku Road
Ernakulam, Kochi - 682016
Kerala
```
Gold (tags: county, locality, no_country):
```
BldgNb: Door No. 12/345A
StrtNm: Pallimukku Road
TwnLctnNm: Ernakulam
TwnNm: Kochi
PstCd: 682016
CtrySubDvsn: Kerala
Ctry: IN
country_hint: IN
```
Question: Is 682016 the Ernakulam / Kochi PIN for this area? (believed correct)

- [ ] Resolved
- My decision: 

## GUIDE?: cases the labelling guide does not decide

### Ireland (IE)

#### `ie-h003`

Raw lines:
```
14 Cnoc na Rí - Ballinteer - Dublin 16 - D16 X0F3 - Eire
```
Gold (tags: country_name, locality, one_line, postal_district):
```
BldgNb: 14
StrtNm: Cnoc na Rí
TwnLctnNm: Ballinteer
TwnNm: Dublin 16
PstCd: D16 X0F3
Ctry: IE
```
Question: 'Cnoc na Rí' is an Irish-language estate name with no street word from the guide's list; labelled StrtNm. Also the dashes: are they separators only?

- [ ] Resolved
- My decision: 

### United Kingdom (GB)

#### `gb-h002`

Raw lines:
```
Dairy Cottage
Farm Lane
Combe Hay
Bath
Somerset BA2 8PH
England
```
Gold (tags: building_name, county, locality, no_country, no_street_number):
```
BldgNm: Dairy Cottage
StrtNm: Farm Lane
TwnLctnNm: Combe Hay
TwnNm: Bath
CtrySubDvsn: Somerset
PstCd: BA2 8PH
Ctry: GB
country_hint: GB
```
Question: Both a county (Somerset) and 'England' on the last line are written; the guide makes each a CtrySubDvsn but there is one field. Gold keeps Somerset only.

- [ ] Resolved
- My decision: 

#### `gb-h003`

Raw lines:
```
3F2, 22 Holm Street
EDINBURGH
EH8 9LZ
UK
```
Gold (tags: country_name, flat):
```
Room: 3F2
BldgNb: 22
StrtNm: Holm Street
TwnNm: EDINBURGH
PstCd: EH8 9LZ
Ctry: GB
```
Question: Scottish tenement flat written as a bare '3F2' with no keyword. Guide says Room keeps its keyword; here there is none.

- [ ] Resolved
- My decision: 

#### `gb-h007`

Raw lines:
```
Thornhill Terrace
12 Keld Road
Sheffield S10 4TG
```
Gold (tags: building_name, no_country):
```
BldgNm: Thornhill Terrace
BldgNb: 12
StrtNm: Keld Road
TwnNm: Sheffield
PstCd: S10 4TG
Ctry: GB
country_hint: GB
```
Question: 'Thornhill Terrace' is a building name but contains a street word (Terrace); guide section 3 would make it a StrtNm. Gold follows the real-world reading (BldgNm).

- [ ] Resolved
- My decision: 

#### `gb-h008`

Raw lines:
```
Flat 4, 9 Stryd Fawr
Caernarfon
LL55 1PT
Wales
```
Gold (tags: county, flat, no_country):
```
Room: Flat 4
BldgNb: 9
StrtNm: Stryd Fawr
TwnNm: Caernarfon
PstCd: LL55 1PT
CtrySubDvsn: Wales
Ctry: GB
country_hint: GB
```
Question: Welsh street word 'Stryd' is not on the guide's street-word list.

- [ ] Resolved
- My decision: 

#### `gb-h010`

Raw lines:
```
Ground Floor Flat
3 Prospect Gardens
Jesmond
Newcastle upon Tyne
NE2 3JW
```
Gold (tags: floor, locality, no_country):
```
Flr: Ground Floor
BldgNb: 3
StrtNm: Prospect Gardens
TwnLctnNm: Jesmond
TwnNm: Newcastle upon Tyne
PstCd: NE2 3JW
Ctry: GB
country_hint: GB
```
Question: 'Ground Floor Flat' has no flat number: Flr 'Ground Floor' labelled, and the word 'Flat' is left unlabelled.

- [ ] Resolved
- My decision: 

#### `gb-h013`

Raw lines:
```
Flat 9 Kingsmead
Weller Park North
Balham
London SW12 8AF
```
Gold (tags: building_name, flat, locality, no_country):
```
Room: Flat 9
BldgNm: Kingsmead
StrtNm: Weller Park North
TwnLctnNm: Balham
TwnNm: London
PstCd: SW12 8AF
Ctry: GB
country_hint: GB
```
Question: Neither 'Kingsmead' (building) nor 'Weller Park North' (street) contains a word from the guide's lists.

- [ ] Resolved
- My decision: 

### France (FR)

#### `fr-h007`

Raw lines:
```
9 boulavard Henri Carpentier
13008 Marseille
```
Gold (tags: no_country, typo):
```
BldgNb: 9
StrtNm: boulavard Henri Carpentier
PstCd: 13008
TwnNm: Marseille
Ctry: FR
country_hint: FR
```
Question: The typo is in the street word itself ('boulavard'). Gold keeps it as written inside StrtNm.

- [ ] Resolved
- My decision: 

#### `fr-h008`

Raw lines:
```
Lieu-dit Kerhoat
56390 Grand-Champ
```
Gold (tags: locality, no_country):
```
TwnLctnNm: Lieu-dit Kerhoat
PstCd: 56390
TwnNm: Grand-Champ
Ctry: FR
country_hint: FR
```
Question: Rural 'lieu-dit' with no street or number: gold labels it TwnLctnNm with the keyword kept ('Lieu-dit Kerhoat').

- [ ] Resolved
- My decision: 

#### `fr-h012`

Raw lines:
```
Rés. Rue Haute - 3 allée des Pins
44000 Nantes
```
Gold (tags: abbreviated, building_name, no_country):
```
BldgNm: Rés. Rue Haute
BldgNb: 3
StrtNm: allée des Pins
PstCd: 44000
TwnNm: Nantes
Ctry: FR
country_hint: FR
```
Question: 'Rés.' (Résidence) is not on the guide's FR abbreviation list, and the building name contains a street word (Rue).

- [ ] Resolved
- My decision: 

### Germany (DE)

#### `de-h001`

Raw lines:
```
Rabenweg 14a
Hinterhaus, 2. OG
10405 Berlin
```
Gold (tags: building_name, floor, no_country):
```
StrtNm: Rabenweg
BldgNb: 14a
BldgNm: Hinterhaus
Flr: 2. OG
PstCd: 10405
TwnNm: Berlin
Ctry: DE
country_hint: DE
```
Question: 'Hinterhaus' (rear building) is not a guide building word ('Haus' is only a separate word); labelled BldgNm.

- [ ] Resolved
- My decision: 

#### `de-h004`

Raw lines:
```
c/o Familie Brandt
Bergstr. 3
69117 Heidelberg
```
Gold (tags: abbreviated, no_country):
```
StrtNm: Bergstr.
BldgNb: 3
PstCd: 69117
TwnNm: Heidelberg
Ctry: DE
country_hint: DE
```
Question: 'c/o Familie Brandt' (care of): CareOf is not used in v1 and the guide does not say how to treat the text. Left unlabelled.

- [ ] Resolved
- My decision: 

#### `de-h010`

Raw lines:
```
Anton-Lenz-Allee 7
81667 München-Haidhausen
```
Gold (tags: no_country):
```
StrtNm: Anton-Lenz-Allee
BldgNb: 7
PstCd: 81667
TwnNm: München-Haidhausen
Ctry: DE
country_hint: DE
```
Question: Town written with its district joined by a hyphen. Gold keeps the whole 'München-Haidhausen' as TwnNm; the guide has no rule for a district joined to a town.

- [ ] Resolved
- My decision: 

### Netherlands (NL)

#### `nl-h005`

Raw lines:
```
Havenkade 22 2hg
3011 TL Rotterdam
```
Gold (tags: no_country):
```
StrtNm: Havenkade
BldgNb: 22 2hg
PstCd: 3011 TL
TwnNm: Rotterdam
Ctry: NL
country_hint: NL
```
Question: '22 2hg' ('2 hoog' = second floor): the guide leaves this form to the hand-written set without saying how to label it. Gold keeps '22 2hg' as BldgNb.

- [ ] Resolved
- My decision: 

#### `nl-h010`

Raw lines:
```
Gebouw De Gracht
Industrieweg 40
2612 XA Delft
```
Gold (tags: building_name, no_country):
```
BldgNm: Gebouw De Gracht
StrtNm: Industrieweg
BldgNb: 40
PstCd: 2612 XA
TwnNm: Delft
Ctry: NL
country_hint: NL
```
Question: The building name 'Gebouw De Gracht' holds both a building word (Gebouw) and a street ending (Gracht).

- [ ] Resolved
- My decision: 

### Canada (CA)

#### `ca-h004`

Raw lines:
```
C.P. 4417, succursale Centre-ville
Sherbrooke (Québec)  J1H 5K9
```
Gold (tags: county, no_country, po_box):
```
PstBx: C.P. 4417
TwnNm: Sherbrooke
CtrySubDvsn: Québec
PstCd: J1H 5K9
Ctry: CA
country_hint: CA
```
Question: 'succursale Centre-ville' (postal station) is part of a PO box address; no field for it, left unlabelled.

- [ ] Resolved
- My decision: 

#### `ca-h006`

Raw lines:
```
#204 - 1177 STANTON ST
VANCOUVER BC
```
Gold (tags: abbreviated, all_caps, county, flat, no_country):
```
Room: #204
BldgNb: 1177
StrtNm: STANTON ST
TwnNm: VANCOUVER
CtrySubDvsn: BC
Ctry: CA
country_hint: CA
```
Question: '#204' as a unit marker: the guide lists '#5' for the US only, not for CA.

- [ ] Resolved
- My decision: 

#### `ca-h011`

Raw lines:
```
RR 3, Site 4, Box 12
Okotoks, AB T1S 2A3
```
Gold (tags: county, no_country):
```
TwnNm: Okotoks
CtrySubDvsn: AB
PstCd: T1S 2A3
Ctry: CA
country_hint: CA
```
Question: Rural route address ('RR 3, Site 4, Box 12'): not covered by the guide. First line left unlabelled.

- [ ] Resolved
- My decision: 

### United States (US)

#### `us-h003`

Raw lines:
```
Marlow Court
910 Wicklow Avenue
Austin, TX 78704
```
Gold (tags: building_name, county, no_country):
```
BldgNm: Marlow Court
BldgNb: 910
StrtNm: Wicklow Avenue
TwnNm: Austin
CtrySubDvsn: TX
PstCd: 78704
Ctry: US
country_hint: US
```
Question: 'Court' is a street word in the US (section 17), so 'Marlow Court' would be a StrtNm, but a second street follows. Gold reads it as a building name.

- [ ] Resolved
- My decision: 

#### `us-h008` (also listed under GUIDE? / VERIFY)

Raw lines:
```
RR 2 Box 14
Bethel, VT 05032
```
Gold (tags: county, no_country, po_box):
```
PstBx: RR 2 Box 14
TwnNm: Bethel
CtrySubDvsn: VT
PstCd: 05032
Ctry: US
country_hint: US
```
Question: Rural route box ('RR 2 Box 14'): the guide only covers 'P.O. Box'. Gold uses PstBx.

- [ ] Resolved
- My decision: 

#### `us-h012`

Raw lines:
```
Bldg 2, Apt 4
5800 Stonebridge Rd
Charlotte, NC 28211
```
Gold (tags: abbreviated, building_name, county, flat, no_country):
```
BldgNm: Bldg 2
Room: Apt 4
BldgNb: 5800
StrtNm: Stonebridge Rd
TwnNm: Charlotte
CtrySubDvsn: NC
PstCd: 28211
Ctry: US
country_hint: US
```
Question: 'Bldg 2' is an abbreviated building identifier; 'Bldg' is not on the guide's abbreviation list and there is no rule for a numbered building.

- [ ] Resolved
- My decision: 

### India (IN)

#### `in-h002`

Raw lines:
```
H.No. 1182, Pocket 3
Sector 12, Dwarka
New Delhi - 110078
```
Gold (tags: abbreviated, locality, no_country):
```
BldgNb: H.No. 1182
TwnLctnNm: Dwarka
TwnNm: New Delhi
PstCd: 110078
Ctry: IN
country_hint: IN
```
Question: 'Pocket 3' and 'Sector 12' are both sub-areas before 'Dwarka'. Gold keeps only 'Dwarka' as TwnLctnNm and leaves 'Pocket 3' and 'Sector 12' unlabelled; 'H.No.' is a form of 'House No.'.

- [ ] Resolved
- My decision: 

#### `in-h003`

Raw lines:
```
#42, 5th Main Road
Koramangala 4th Block
Bengaluru, Karnataka 560034
```
Gold (tags: county, locality, no_country):
```
BldgNb: #42
StrtNm: 5th Main Road
TwnLctnNm: Koramangala 4th Block
TwnNm: Bengaluru
CtrySubDvsn: Karnataka
PstCd: 560034
Ctry: IN
country_hint: IN
```
Question: '#42' as a house number: the guide's BldgNb keywords are Plot / House No. / Door No.; '#' is not covered.

- [ ] Resolved
- My decision: 

#### `in-h005`

Raw lines:
```
Bungalow 7, Sutar Wadi Road
Aundh, Pune, MH
```
Gold (tags: county, locality, no_country):
```
BldgNb: Bungalow 7
StrtNm: Sutar Wadi Road
TwnLctnNm: Aundh
TwnNm: Pune
CtrySubDvsn: MH
Ctry: IN
country_hint: IN
```
Question: 'Bungalow 7' as a house number with its keyword; the guide lists Plot, House No. and Door No. only.

- [ ] Resolved
- My decision: 

#### `in-h006`

Raw lines:
```
SCO 118-119, Sector 17-C
Chandigarh 160017
```
Gold (tags: locality, no_country):
```
BldgNb: SCO 118-119
TwnLctnNm: Sector 17-C
TwnNm: Chandigarh
PstCd: 160017
Ctry: IN
country_hint: IN
```
Question: 'SCO' (shop-cum-office) number as BldgNb with its keyword, by analogy with Plot and House No.

- [ ] Resolved
- My decision: 

#### `in-h007`

Raw lines:
```
Gali No. 5, Shiv Mandir ke paas
Laxmi Nagar
Delhi 110092
```
Gold (tags: landmark, locality, no_country):
```
StrtNm: Gali No. 5
TwnLctnNm: Laxmi Nagar
TwnNm: Delhi
PstCd: 110092
Ctry: IN
country_hint: IN
```
Question: 'Gali' (Hindi for lane) is not on the guide's street-word list; the landmark 'Shiv Mandir ke paas' ('near the Shiv temple') is in Hinglish.

- [ ] Resolved
- My decision: 

#### `in-h008`

Raw lines:
```
NEW NO. 12, OLD NO. 7, 2ND STREET
ADYAR
CHENNAI - 600020
TAMIL NADU
```
Gold (tags: all_caps, county, locality, no_country):
```
StrtNm: 2ND STREET
TwnLctnNm: ADYAR
TwnNm: CHENNAI
PstCd: 600020
CtrySubDvsn: TAMIL NADU
Ctry: IN
country_hint: IN
```
Question: Chennai 'New No. / Old No.' door numbers: the guide has no rule for two numbers. Both left unlabelled.

- [ ] Resolved
- My decision: 

#### `in-h012`

Raw lines:
```
House No. 118, Near Church Square
Candolim
Bardez, Goa 403515
```
Gold (tags: county, landmark, no_country):
```
BldgNb: House No. 118
TwnNm: Candolim
CtrySubDvsn: Goa
PstCd: 403515
Ctry: IN
country_hint: IN
```
Question: Goa address: 'Candolim' is a village and 'Bardez' the taluka (sub-district). Gold takes Candolim as TwnNm and leaves 'Bardez' unlabelled.

- [ ] Resolved
- My decision: 

