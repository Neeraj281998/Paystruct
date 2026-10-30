# Hard set: how it was made and the decisions in it

Date: 2026-10-30. Status: accepted by delegation (the project owner handed the review to the AI and has not read these decisions; audit them here).

## Provenance and size

- The entries were **drafted with AI assistance**, then **reviewed and corrected by the AI** against public sources and the principles below. They were **not manually reviewed by the project owner**, and none was written or rewritten by the owner. The set is not called hand-written anywhere. Every file starts with: "AI-drafted and AI-reviewed against public sources; not manually reviewed by the project owner."
- The draft had 100 entries. The set is cut to **N = 40**, 5 per country (IE, GB, FR, DE, NL, CA, US, IN). Difficulty tiers as built: 34 hard, 5 medium, 1 easy. 5 entries are `no_town` (ie-h005, gb-h006, fr-h004, ca-h007, in-h004). Ids keep their draft numbers, so they have gaps.
- `build_hard_set.py` now takes `--min-entries` (default 40) instead of demanding exactly 100. The validator is as strict as before. A new tag, `unlabelled_text`, marks entries with text that no field fits (it does not change the difficulty tier).
- The set is an independent check on generator and GeoNames circularity only to the extent it is independent of the AI that also wrote parts of this project. It is not human-written real-world data, and the write-up must say so.

## Principles (applied to every decision below)

1. Gold follows the real-world meaning of the address, kept exactly as written, never expanded or corrected.
2. If no XSD field fits a piece of text, leave it unlabelled and tag it (`landmark` or `unlabelled_text`). Never force it into the nearest field.
3. A value that cannot be verified is not kept. Never guess.
4. The guide's word lists are generator heuristics; a clear real-world reading wins and the entry carries a `note`.

## Which 40 were kept, and why

Dropped: template-like entries (a plain number, street, town and postcode in natural order with a flat or building name added) and entries that repeated a case already covered.

- **IE:** ie-h003 (one line, Irish estate name, Dublin 16, "Eire"), ie-h005 (no town, lone routing key), ie-h006 (Dublin 3 district, floor, locality), ie-h010 (reordered one-liner, verified), ie-h012 (lower case, no postcode space, Dublin 2).
- **GB:** gb-h002 (county plus "England"), gb-h003 (Scottish tenement flat, "UK"), gb-h005 (one line, no commas, lone outward code), gb-h006 (no town, no postcode), gb-h012 (postcode split across lines).
- **FR:** fr-h002 (BP and Cedex, verified), fr-h004 (no town), fr-h007 (typo in the street word), fr-h011 (arrondissement, no postcode), fr-h012 (building name with a street word).
- **DE:** de-h001 (Hinterhaus), de-h002 (Postfach, verified), de-h004 (c/o), de-h010 (district joined to town), de-h012 (English flat words in a German one-liner).
- **NL:** nl-h002 (Postbus, verified), nl-h004 (English unit and floor in a Dutch address), nl-h005 ("2hg"), nl-h006 (slash-separated one-liner, "Nederland"), nl-h008 (reordered).
- **CA:** ca-h002 (the ", CA" suffix, which here is the country and not a state), ca-h004 (C.P. with a station), ca-h006 (#204 unit, all caps), ca-h007 (no town, French), ca-h011 (rural route).
- **US:** us-h001 (", CA" as the state California), us-h003 (building name with "Court"), us-h006 (Hawaii "94-" number, verified), us-h007 (all-caps one-liner, "U.S.A."), us-h008 (rural route box, verified).
- **IN:** in-h002 (Pocket, Sector, locality), in-h004 (no town, locality only), in-h007 (Gali and a Hinglish landmark), in-h008 (New No. and Old No.), in-h012 (Goa, taluka and landmark).

## Decisions on the GUIDE? items that were kept

Rule numbers refer to `data/labelling-guide.md` section 21 (16 new rules).

| Entry | Question | Decision | Reason |
|---|---|---|---|
| ie-h003 | Irish estate name with no street word; are the dashes separators? | `StrtNm` "Cnoc na Rí"; dashes are separators. Gold unchanged. | It stands where a street goes (21.1, 21.2). |
| gb-h002 | County and "England" both written, one field | `CtrySubDvsn` "Somerset"; England unlabelled; tag `unlabelled_text` added. | More specific wins (21.4); principle 2. |
| gb-h003 | Bare "3F2" with no keyword | `Room` "3F2". Unchanged. | Real-world reading: a tenement flat identifier (21.5). |
| fr-h007 | Typo in the street word | `StrtNm` "boulavard Henri Carpentier". Unchanged. | Gold is never corrected (21.6, guide 9). |
| fr-h012 | "Rés." not on the abbreviation list, "Rue" inside a building name | `BldgNm` "Rés. Rue Haute". Unchanged; note says "Rés." is not on the scorer allowlist. | Real-world reading beats the word list (21.3). |
| de-h001 | "Hinterhaus" is not a guide word | `BldgNm` "Hinterhaus". Unchanged. | It names a building in the premises (21.7). |
| de-h004 | "c/o Familie Brandt" | Unlabelled; tag `unlabelled_text` added. | No field (`CareOf` unused) (21.8). |
| de-h010 | District joined to town | **Changed:** `TwnNm` "München" and `TwnLctnNm` "Haidhausen" (was `TwnNm` "München-Haidhausen"); tag `locality` added. | Haidhausen is a Munich district and 81667 lies in it (see verification); a system that keeps the joined form is grounded but not equal to gold (21.2, 21.9). |
| nl-h005 | "22 2hg" | **Changed:** `BldgNb` "22" and `Flr` "2hg" (was `BldgNb` "22 2hg"); tag `floor` added. | "2 hoog" is the second floor, and a field fits (21.10). |
| ca-h004 | Postal station in a PO box address | Station unlabelled; tag `unlabelled_text` added. | No field (21.11). |
| ca-h006 | "#204" as a unit in CA | `Room` "#204". Unchanged. | Real-world reading; extends the US rule (21.12). |
| ca-h011 | Rural route | Unlabelled; tag `unlabelled_text` added. | No field; not a PO box (21.13). |
| us-h003 | "Court" is a US street word, but a second street follows | `BldgNm` "Marlow Court". Unchanged. | Stand-alone line before a numbered street (21.3). |
| us-h008 | "RR 2 Box 14" and `PstBx` | **Changed:** `PstBx` removed, line unlabelled, tag `po_box` replaced by `unlabelled_text`. | A rural-route box is not a PO box (21.13). |
| in-h002 | Pocket 3 and Sector 12 before Dwarka | **Changed:** `TwnLctnNm` "Sector 12, Dwarka" (was "Dwarka"); "Pocket 3" unlabelled; tag `unlabelled_text` added. | One field; the last phrase as written, with its sector (21.14). |
| in-h007 | "Gali" not on the street-word list | `StrtNm` "Gali No. 5"; landmark unlabelled. Unchanged. | Gali is Hindi for lane (21.1). |
| in-h008 | Two door numbers | **Changed:** `BldgNb` "NEW NO. 12" added; "OLD NO. 7" unlabelled; tag `unlabelled_text` added. | The current number is the door number; the old one is superseded (21.15). |
| in-h012 | Village and taluka | `TwnNm` "Candolim"; "Bardez" unlabelled; tag `unlabelled_text` added. | PIN 403515 is Candolim's (verified); taluka has no field (21.16). |

## Decisions on the VERIFY items

See `docs/hard-set-verification.md`. One entry changed (fr-h002: postcode 69256 to 69264). **Entries dropped for failed verification: 0.**

## Known weaknesses

- Several decisions (de-h010, nl-h005, in-h002, in-h008) are judgement calls; a reasonable annotator could label them differently, so those entries mainly test whether a system stays grounded and goes to review when unsure.
- Unflagged postcodes were not checked one by one; only routing-key, area or ZIP level can be checked from public sources.
- Section 21 of the guide was written by the AI.
