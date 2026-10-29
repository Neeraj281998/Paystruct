#!/usr/bin/env python3
"""Derives data/generator/addrgen/data/postcode_ties.json from the GeoNames postal code files.

The JSON holds, for US, DE and IN, the postcodes GeoNames lists for each town the generator writes, and for GB the
outward codes of each locality. The GeoNames files (CC BY 4.0, https://www.geonames.org) are in
data/reference/geonames-postal/ and are not committed; the derived JSON is. Pairings GeoNames cannot confirm and that
are kept anyway (from memory, flagged) are listed under "unconfirmed".
"""
import json
import re
from collections import defaultdict

import _path  # noqa: F401
import audit_postcode_ties as a
from addrgen.countries import de, gb, in_, us

OUT = _path.REPO_ROOT / "data" / "generator" / "addrgen" / "data" / "postcode_ties.json"
SECTOR = re.compile(r"sector[\s\-]*(\d+)")

# Locality PINs written from memory; used only if the PIN is one GeoNames lists for the city, and flagged unconfirmed.
MEMORY_LOCALITY_PINS = {
    ("Pune", "Koregaon Park"): ("411001",), ("Pune", "Kothrud"): ("411038",), ("Pune", "Viman Nagar"): ("411014",),
    ("Pune", "Hinjewadi"): ("411057",), ("Pune", "Baner"): ("411045",), ("Pune", "Aundh"): ("411007",),
    ("Mumbai", "Andheri East"): ("400069", "400093", "400059"), ("Mumbai", "Bandra West"): ("400050",),
    ("Mumbai", "Powai"): ("400076",), ("Mumbai", "Juhu"): ("400049",), ("Mumbai", "Dadar"): ("400014", "400028"),
    ("Mumbai", "Borivali West"): ("400092",),
    ("Bengaluru", "Koramangala"): ("560034", "560095"), ("Bengaluru", "Indiranagar"): ("560038",),
    ("Bengaluru", "Whitefield"): ("560066",), ("Bengaluru", "HSR Layout"): ("560102",),
    ("Bengaluru", "Jayanagar"): ("560011", "560041"),
    ("Chennai", "T. Nagar"): ("600017",), ("Chennai", "Adyar"): ("600020",), ("Chennai", "Anna Nagar"): ("600040",),
    ("Chennai", "Velachery"): ("600042",),
    ("New Delhi", "Connaught Place"): ("110001",), ("New Delhi", "Saket"): ("110017",),
    ("New Delhi", "Dwarka"): ("110075", "110077", "110078"), ("New Delhi", "Karol Bagh"): ("110005",),
    ("New Delhi", "Lajpat Nagar"): ("110024",),
    ("Hyderabad", "Banjara Hills"): ("500034",), ("Hyderabad", "Jubilee Hills"): ("500033",),
    ("Hyderabad", "Madhapur"): ("500081",), ("Hyderabad", "Gachibowli"): ("500032",),
    ("Kolkata", "Salt Lake"): ("700091", "700064", "700106"), ("Kolkata", "Ballygunge"): ("700019",),
    ("Kolkata", "Behala"): ("700034", "700060"), ("Kolkata", "New Town"): ("700156",),
    ("Ahmedabad", "Navrangpura"): ("380009",), ("Ahmedabad", "Satellite"): ("380015",),
    ("Ahmedabad", "Maninagar"): ("380008",), ("Ahmedabad", "Vastrapur"): ("380015",),
    ("Jaipur", "Malviya Nagar"): ("302017",), ("Jaipur", "C-Scheme"): ("302001",),
    ("Jaipur", "Vaishali Nagar"): ("302021",), ("Jaipur", "Mansarovar"): ("302020",),
    ("Lucknow", "Gomti Nagar"): ("226010",), ("Lucknow", "Hazratganj"): ("226001",), ("Lucknow", "Aliganj"): ("226024",),
}


def us_zips(data):
    out = {}
    for city, code, _name, _ in us.CITIES:
        out[city] = sorted(c for c, rows in data.items() if any(r[0] == a.fold(city) and r[2] == code for r in rows))
    return out


def de_codes(data):
    out = {}
    for town, _ in de.TOWNS:  # geographic place names only: GeoNames also lists corporate codes under company names
        t = a.fold(town)
        out[town] = sorted(c for c, rows in data.items() if any(r[0] == t or r[0].startswith(t + " ") for r in rows))
    return out


def in_ties(data):
    cities, localities, sectors = {}, {}, {}
    untied, memory = [], []
    for town, state, _prefix, locs in in_.CITIES:
        aliases = a.IN_ALIASES.get(town.casefold(), (town.casefold(),))
        rows_by_pin = defaultdict(list)
        for pin, rows in data.items():
            if not pin.startswith(_prefix):  # villages of the wider district have other prefixes; keep the city's own
                continue
            for r in rows:
                if r[1] == a.fold(state) and any(x in r[0] or x in r[4] for x in aliases):
                    rows_by_pin[pin].append(r)
        cities[town] = sorted(rows_by_pin)
        sector_map = defaultdict(set)
        for pin, rows in rows_by_pin.items():
            for r in rows:
                m = SECTOR.search(r[0])
                if m:
                    sector_map[int(m.group(1))].add(pin)
        if any("{n}" in loc for loc in locs):  # a sector is written only if GeoNames gives its PIN
            sectors[town] = {str(n): sorted(p)[0] for n, p in sorted(sector_map.items()) if len(p) == 1}
        for loc in locs:
            if "{n}" in loc:
                continue
            seen = sorted({pin for pin, rows in rows_by_pin.items() if any(a.ascii_fold(loc).rstrip(".") in a.ascii_fold(r[0]) for r in rows)})
            if seen:
                localities[f"{town}|{loc}"] = {"pins": seen, "basis": "geonames"}
                continue
            mem = [p for p in MEMORY_LOCALITY_PINS.get((town, loc), ()) if p in rows_by_pin]
            if mem:
                localities[f"{town}|{loc}"] = {"pins": mem, "basis": "memory"}
                memory.append(f"{loc}, {town}: {', '.join(mem)}")
            else:
                untied.append(f"{loc}, {town}")
    return {"cities": cities, "localities": localities, "sectors": sectors}, untied, memory


def gb_ties(data):
    out, untied = {}, []
    for town, outwards, county, constituent, locs in gb.POST_TOWNS:
        areas = {re.match(r"[A-Z]+", o).group() for o in outwards}
        if town == "London":
            areas |= {"E", "EC", "N", "NW", "SE", "SW", "W", "WC"}
        for loc in locs:
            codes = sorted({c for c, rows in data.items() if re.match(r"[A-Z]+", c).group() in areas
                            and any(a.ascii_fold(r[0]) == a.ascii_fold(loc) and r[2] == a.GB_CONSTITUENT[constituent] for r in rows)})
            if codes:
                out[f"{town}|{loc}"] = codes
            else:
                untied.append(f"{loc}, {town}")
    return out, untied


def main() -> int:
    in_data, gb_data = a.load("IN"), a.load("GB")
    in_json, in_untied, in_memory = in_ties(in_data)
    gb_json, gb_untied = gb_ties(gb_data)
    result = {
        "source": "GeoNames postal code data, CC BY 4.0, https://www.geonames.org (GB: Royal Mail data, see GeoNames readme)",
        "US": us_zips(a.load("US")), "DE": de_codes(a.load("DE")), "IN": in_json, "GB": {"localities": gb_json},
        "unconfirmed": {"IN_locality_pin_from_memory": in_memory, "IN_locality_without_pin_tie": in_untied,
                        "GB_locality_without_outward_tie": gb_untied},
    }
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(_path.REPO_ROOT)} ({OUT.stat().st_size // 1024} KB)")
    print("US zips per city:", {k: len(v) for k, v in result["US"].items()})
    print("DE codes per town:", {k: len(v) for k, v in result["DE"].items()})
    print("IN PINs per city:", {k: len(v) for k, v in in_json["cities"].items()})
    print("IN sectors:", {k: len(v) for k, v in in_json["sectors"].items()})
    print(f"IN localities: {sum(1 for v in in_json['localities'].values() if v['basis'] == 'geonames')} GeoNames, "
          f"{len(in_memory)} memory, {len(in_untied)} untied")
    print(f"GB localities: {len(gb_json)} tied, {len(gb_untied)} untied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
