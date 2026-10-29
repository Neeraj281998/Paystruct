#!/usr/bin/env python3
"""Checks the generator's postcode-to-town tables against the GeoNames postal code files.

GeoNames files (CC BY 4.0) live in data/reference/geonames-postal/ and are not committed. For every country with a file
(CA, DE, FR, GB, IE, IN, NL, US) this reports, per table entry (a "pairing": town with a postcode prefix, range, or code), whether
the file confirms it, contradicts it, or cannot cover it, and the same for every postcode the generator could emit.
IE (routing keys), GB (outward codes) and CA (first three characters) carry no full codes, so they are checked at that level. Set ADDRGEN_DIR to another copy of data/generator to audit a draft.
"""
import argparse
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import os

import _path  # noqa: F401

if os.environ.get("ADDRGEN_DIR"):  # audit another copy of the generator (a draft) instead of the repository's
    sys.path.insert(0, os.environ["ADDRGEN_DIR"])
from addrgen import countries  # noqa: E402,F401

REF = _path.REPO_ROOT / "data" / "reference" / "geonames-postal"
fold = lambda s: unicodedata.normalize("NFC", s).casefold()
ascii_fold = lambda s: "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).casefold()
GB_CONSTITUENT = {"England": "ENG", "Scotland": "SCT", "Wales": "WLS", "Northern Ireland": "NIR"}


def load(code: str) -> dict[str, list[tuple]]:
    """postal code -> rows of (place, admin1 name, admin1 code, admin2 name, admin3 name)."""
    out = defaultdict(list)
    with open(REF / f"{code}.txt", encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            out[p[1]].append((fold(p[2]), fold(p[3]), p[4], fold(p[5]), fold(p[7]) if len(p) > 7 else ""))
    return out


IN_ALIASES = {"new delhi": ("delhi",), "mumbai": ("mumbai", "bombay"), "bengaluru": ("bangalore", "bengaluru"),
              "kolkata": ("kolkata", "calcutta"), "gurugram": ("gurgaon", "gurugram"),
              "noida": ("noida", "gautam buddha nagar"), "hyderabad": ("hyderabad",)}


def row_is_town(country: str, town: str, state: str | None, row: tuple) -> bool:
    place, adm1, adm1code, adm2, adm3 = row
    t = fold(town)
    if country == "US":
        return place == t and adm1code == state
    if country == "DE":
        return place.startswith(t) or t in adm3 or t in adm2
    if country == "NL":
        return t in (place, adm2.removeprefix("gemeente ")) or (t == "den haag" and place == "'s-gravenhage")
    if country == "FR":
        return place == t or place.startswith(t + " ")
    if country == "IN":
        return any(a in place or a in adm2 or a in adm3 for a in IN_ALIASES.get(t, (t,)))
    if country == "IE":  # GeoNames has routing keys only, with province, so the county cannot be checked
        return ascii_fold(town) in ascii_fold(place) if not town.startswith("Dublin") else place.startswith(t)
    if country == "CA":  # first three characters only; the province code is checked too
        names = ascii_fold(" | ".join((place, adm2, adm3)))  # neighbourhood names: the city is in the administrative area
        return ascii_fold(town) in names and adm1code == state
    if country == "GB":  # outward codes only; place names are localities, so the post town is often not listed
        return ascii_fold(town) in ascii_fold(place)
    raise ValueError(country)


def gb_area_ok(town: str, county: str | None, constituent: str, row: tuple) -> bool:
    """Weaker GB check: the code lies in the right constituent country and, when we write one, the right county."""
    _place, _adm1, adm1code, adm2, _adm3 = row
    return adm1code == GB_CONSTITUENT[constituent] and (county is None or fold(county) in adm2 or adm2 in fold(county))


def pairings(country: str):
    """(town, state, label, codes) for each table entry, read from the generator's own tables."""
    m = sys.modules[f"addrgen.countries.{ {'IN': 'in_'}.get(country, country.lower()) }"]
    if country == "US":
        for city, code, _name, zips in m.CITIES:
            yield city, code, "listed ZIPs", list(zips)
    elif country == "DE":
        for town, codes in m.TOWNS:
            yield town, None, "listed postcodes", list(codes)
    elif country == "NL":
        for town, lo, hi in m.TOWNS:
            yield town, None, f"{lo}-{hi}", [str(z) for z in range(lo, hi + 1)]
    elif country == "FR":
        for town, codes in m.PLAIN_TOWNS:
            for c in codes:
                yield town, None, c, [c]
        for town, prefix, count in m.ARRONDISSEMENT_TOWNS:
            yield town, None, f"{prefix}01-{prefix}{count:02d}", [f"{prefix}{n:02d}" for n in range(1, count + 1)]
    elif country == "IE":
        for town, _county, key, _locs in m.TOWNS:
            yield town, None, key, [key]
        for written, key in m.DUBLIN_DISTRICTS:
            yield written, None, key, [key]
    elif country == "GB":
        for town, outwards, county, constituent, _locs in m.POST_TOWNS:
            for o in outwards:
                yield town, (county, constituent), o, [o]
    elif country == "CA":
        for town, prov, _name, fsas, _fr in m.TOWNS:
            for f in fsas:
                yield town, prov, f, [f]
    elif country == "IN":
        from addrgen.ties import ties

        for town, state, _prefix, _locs in m.CITIES:
            yield town, state, "listed PINs", list(ties()["IN"]["cities"][town])


def audit(country: str, verbose: bool) -> None:
    data = load(country)
    if country == "GB":
        return audit_gb(data, verbose)
    verdicts = defaultdict(int)
    emit = defaultdict(int)
    detail = []
    # IE lists one place per routing key and CA names neighbourhoods, so a name that differs is not a contradiction.
    soft = country in ("IE", "CA")
    for town, state, label, codes in pairings(country):
        for c in codes:  # emit level: every postcode the generator could write for this pairing
            rows = data.get(c)
            emit["absent" if not rows else "confirmed" if any(row_is_town(country, town, state, r) for r in rows)
                 else "absent" if soft else "contradicted"] += 1
        present = [c for c in codes if c in data]
        good = [c for c in present if any(row_is_town(country, town, state, r) for r in data[c])]
        if not present:
            v = "cannot cover"
        elif len(good) == len(present):
            v = "confirmed"
        elif not good:
            v = "cannot cover" if soft else "contradicted"
        else:
            v = "mixed"
        verdicts[v] += 1
        if v != "confirmed":
            detail.append(f"    {v:12} {town} {label}: {len(good)} of {len(present)} listed codes are {town}"
                          + (f" (e.g. {[(c, data[c][0][0]) for c in present if c not in good][:2]})" if v in ("contradicted", "mixed") else ""))
    n = sum(verdicts.values())
    e = sum(emit.values())
    print(f"{country}: {n} pairings: " + ", ".join(f"{k} {verdicts[k]}" for k in ("confirmed", "mixed", "contradicted", "cannot cover")))
    print(f"    postcodes the generator can emit ({e}): " + ", ".join(
        f"{k} {emit[k]} ({100 * emit[k] / e:.0f}%)" for k in ("confirmed", "contradicted", "absent")))
    if verbose:
        print("\n".join(detail))


def audit_gb(data, verbose: bool) -> None:
    counts = defaultdict(int)
    detail = []
    for town, (county, constituent), code, _ in pairings("GB"):
        rows = data.get(code)
        if not rows:
            v = "cannot cover (code not in file)"
        elif any(row_is_town("GB", town, None, r) for r in rows):
            v = "confirmed (post town listed at the code)"
        elif any(gb_area_ok(town, county, constituent, r) for r in rows):
            v = "cannot cover (right county/country, town not listed)"
        else:
            v = "contradicted"
        counts[v] += 1
        if verbose and not v.startswith("confirmed"):
            detail.append(f"    {v.split(' (')[0]:12} {town} {code}: file says {sorted({(r[0], r[3]) for r in rows})[:3]}")
    print(f"GB: {sum(counts.values())} pairings (post town x outward code): " + "; ".join(f"{k} {n}" for k, n in sorted(counts.items())))
    print("\n".join(detail))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("-v", "--verbose", action="store_true", help="list every pairing that is not fully confirmed")
    args = p.parse_args()
    for c in ("US", "IN", "DE", "NL", "FR", "IE", "GB", "CA"):
        audit(c, args.verbose)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
