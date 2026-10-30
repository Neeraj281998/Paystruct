# Hard-set verification

Checked 2026-10-30 by web search (the AI, not the project owner). Each row is a claim an entry makes about a postcode and its town. A claim that could not be confirmed was changed or the entry dropped. The street names, house numbers and PO box numbers in the entries are synthetic; only the pairing of postcode and town was checked.

Limits: the checks are at the level the source allows (a routing key, a four-digit area, a ZIP, a Cedex code). Full Eircodes, UK inward codes and Dutch letter pairs are not individually checkable and are not claimed. Entries without a VERIFY comment in the original draft were not checked one by one.

| Entry | Claim | Source | Conclusion |
|---|---|---|---|
| ie-h010 | Eircode routing key V15 is Kilrush, Co. Clare | https://en.wikipedia.org/wiki/List_of_Eircode_routing_areas_in_Ireland (Kilrush, Clare listed for V15); full Eircodes V15 KT04 (Kilrush Community School) and V15 ED61 (Kilrush Courthouse) found in listings | Confirmed at routing-key level. Kept. |
| fr-h002 | 69256 is the Cedex code of Lyon Cedex 09 | https://www.annuaire-administration.com/commune/lyon-9e-arrondissement-69009.html gives "BP 9201, 69264 Lyon Cedex 9" for the Lyon 9e town hall. 69256 is the INSEE code of Vaulx-en-Velin (https://www.insee.fr/fr/metadonnees/geographie/commune/69256-vaulx-en-velin) | **Not confirmed; contradicted.** Postcode changed to 69264 (confirmed Lyon Cedex 9 code). Kept. |
| de-h002 | 70049 is a Stuttgart Postfach postcode | https://www.finanzamt24.de/finanzamt-stuttgart/ lists "Rotebühlplatz 30, 70173 Stuttgart, Postfach 106055, 70049 Stuttgart" | Confirmed. Kept; keeps tag `not_in_geonames` (70049 is not a street postcode). |
| nl-h002 | 3503 RK is a Utrecht Postbus postcode | The City of Utrecht's own map document (https://www.utrecht.nl/fileadmin/uploads/documenten/wonen-en-leven/parken-en-groen/parken-en-plantsoenen/zocherpark/Kaart-Zocherpark.pdf) gives its postal address as "postbus 8406, 3503 RK UTRECHT" | Confirmed. Kept. |
| us-h006 | 96797 is the Waipahu, HI ZIP | https://www.zip-codes.com/zip-code/96797/zip-code-96797.asp and https://www.zip-codes.com/city/hi-waipahu.asp (96797 is Waipahu's ZIP); "94-" Waipahu addresses use 96797 (e.g. 94-1039 Hohola Street, https://www.hawaii.house/home/94-1039-hohola-street-waipahu-hi-96797-oahu/202208223/) | Confirmed. The street "Hokua Street" was not found and is synthetic. Kept. |
| us-h008 | 05032 is the Bethel, VT ZIP | https://www.zip-codes.com/zip-code/05032/zip-code-05032.asp and https://www.zip-codes.com/city/vt-bethel.asp | Confirmed. Kept. |
| in-h012 | PIN 403515 is Candolim, Bardez, North Goa | https://pin.codes.in/pincode/403515/candolim-s-o and https://www.mapsofindia.com/pincode/india/goa/north-goa/candolim.html | Confirmed (not a draft VERIFY item; checked because the entry splits Candolim from Bardez). Kept. |
| de-h010 | Haidhausen is a district of München and 81667 lies in it | https://www.muenchenwiki.de/wiki/Au-Haidhausen (81667 is listed for the Au-Haidhausen district); https://onlinestreet.de/plz/M%C3%BCnchen.Haidhausen.html | Confirmed (not a draft VERIFY item; checked because the entry splits town and district). Kept. |

## Dropped before verification (not for failed verification)

in-h011 (Kochi 682016) and us-h004 (Boise 83707) were VERIFY items that were left out of the 40-entry keep list on difficulty and balance grounds, so they were not checked. **Entries dropped for failed verification: 0.**
