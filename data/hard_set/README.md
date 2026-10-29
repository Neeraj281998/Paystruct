# Hand-written hard set

The 100 addresses in this set are written by hand, outside the generator's patterns, so a system tuned on generator output cannot look better than it is. Aim for about 12 per country (100 in total).

One file per country, `IE.yaml`, `GB.yaml`, ... Every entry:

```yaml
- id: ie-h001              # country code, h, three digits. Examples use x01, x02 and example: true.
  tags: [county, no_country]   # corruption and structure tags from labelling-guide.md section 11
  raw_lines:               # the address as it arrives: at most 7 lines, each at most 70 characters
    - "Forge House"
    - "Kinvara, Co. Galway H91 W3R7"
  gold:                    # element names from the XSD; values copied from the raw lines
    BldgNm: "Forge House"
    TwnNm: "Kinvara"
    CtrySubDvsn: "Co. Galway"
    PstCd: "H91 W3R7"
    Ctry: IE               # the only value allowed to be missing from the raw lines
  country_hint: IE         # only with the no_country tag
  note: ""                 # optional
```

Rules the validator enforces: `TwnNm` and `Ctry` are required (`TwnNm` is absent, and must be, in entries tagged `no_town`, guide section 20); `Ctry` equals the file's country; every other gold value appears in the raw lines exactly as written (guide section 0); lengths and patterns come from the XSD; tags are known tags (including the optional `partial_postcode`, `not_in_geonames` and `no_town`, which do not change the difficulty tier); ids are unique. The difficulty tier is computed from the tags (guide section 11), so you do not write it. Landmarks and any text with no field stay out of gold (guide section 18).

Entries with `example: true` only show the format. They are left out of `hard.jsonl` and you delete them when you write your own.

```bash
data/generator/.venv/bin/python scripts/validate_hard_set.py             # check the files
data/generator/.venv/bin/python scripts/build_hard_set.py                # write data/splits/hard.jsonl (exactly 100 real entries)
data/generator/.venv/bin/python scripts/build_hard_set.py --allow-partial   # while you are still writing
```
