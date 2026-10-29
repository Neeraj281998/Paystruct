"""Places generated addresses into pacs.008 and pain.001 skeletons and validates them against the XSDs.

Every message carries two address jobs, a debtor and a creditor, as unstructured `AdrLine` text (the form PayStruct
reads). The bank of each party has a BIC whose country letters match the address, so a missing country in the text
still has a hint, as in Phase 1. A job may get one message-level fault (below); gold never changes, because a fault
only moves or removes text.
"""
from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from lxml import etree

from addrgen import countries
from addrgen.limits import MAX_LINE_LENGTH, MAX_LINES, PACS008_XSD, PAIN001_XSD

FAULTS = ("missing_country", "too_many_lines", "town_in_line")
PACS008, PAIN001 = "pacs.008", "pain.001"
_NS = {PACS008: "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.14", PAIN001: "urn:iso:std:iso:20022:tech:xsd:pain.001.001.13"}
_XSD = {PACS008: PACS008_XSD, PAIN001: PAIN001_XSD}
_PREFIX = {PACS008: "pacs008", PAIN001: "pain001"}
FAULT_RATE = 0.3  # share of jobs that get a fault

# Invented company names; no real organisations.
_NAME_A = ("Brindle", "Harbour", "Fernhill", "Saffron", "Tulip", "Marrow", "Copper", "Alder", "Lantern", "Quarry",
           "Willow", "Granite", "Juniper", "Sparrow", "Cobalt", "Meadow")
_NAME_B = ("Moss", "Lights", "Foods", "Exports", "Handel", "Works", "Supply", "Logistics", "Textiles", "Trading",
           "Systems", "Design", "Freight", "Print", "Timber", "Labs")
_FORM = {"IE": "Ltd", "GB": "Ltd", "FR": "SARL", "DE": "GmbH", "NL": "BV", "CA": "Inc", "US": "LLC", "IN": "Pvt Ltd"}
_CURRENCY = {"IE": "EUR", "GB": "GBP", "FR": "EUR", "DE": "EUR", "NL": "EUR", "CA": "CAD", "US": "USD", "IN": "INR"}


# ---- message-level faults -------------------------------------------------------------------------------------

def _country_forms(country: str) -> list[str]:
    module = countries.get(country)
    return sorted({*module.country_names, module.code}, key=len, reverse=True)


def fault_missing_country(record: dict) -> list[str] | None:
    """The lines with the country text removed from the end, or None if there is no country text to remove."""
    if "no_country" in record["tags"]:
        return None
    lines = list(record["raw_lines"])
    last = lines[-1]
    for form in _country_forms(record["country"]):
        m = re.search(rf"(?:^|[\s,]){re.escape(form)}[\s,.]*$", last, flags=re.IGNORECASE)
        if m is None:
            continue
        rest = last[:m.start()].rstrip(" ,")
        lines = lines[:-1] + ([rest] if rest.strip() else [])
        return lines or None
    return None


def fault_too_many_lines(record: dict) -> list[str] | None:
    """The same text on MAX_LINES + 1 lines, cut at spaces, or None if the text is too short to cut."""
    lines = list(record["raw_lines"])
    while len(lines) <= MAX_LINES:
        candidates = [i for i, line in enumerate(lines) if " " in line.strip()]
        if not candidates:
            return None
        i = max(candidates, key=lambda k: len(lines[k]))
        line = lines[i].strip()
        spaces = [m.start() for m in re.finditer(" ", line)]
        cut = min(spaces, key=lambda s: abs(s - len(line) / 2))
        lines[i:i + 1] = [line[:cut].rstrip(), line[cut:].lstrip()]
    return lines


def fault_town_in_line(record: dict) -> list[str] | None:
    """The town moved up onto the previous line, with whatever stood before it on its own line (so token order is
    kept). None if the town is on the first line, is split over lines, or would make the line too long."""
    town = record["gold"].get("TwnNm")
    lines = list(record["raw_lines"])
    if not town:
        return None
    for i in range(len(lines) - 1, 0, -1):  # the last line holding the town, never the first line
        # Whole words only: the town "Oxford" is not the start of the county "Oxfordshire".
        found = list(re.finditer(rf"(?<!\w){re.escape(town)}(?!\w)", lines[i], flags=re.IGNORECASE))
        if not found:
            continue
        pos, end = found[-1].span()
        if lines[i][end:end + 1] == ",":
            end += 1
        moved, rest = lines[i][:end].strip(), lines[i][end:].strip()
        merged = f"{lines[i - 1].rstrip()} {moved}"
        if len(merged) > MAX_LINE_LENGTH:
            return None
        lines[i - 1:i + 1] = [merged] + ([rest] if rest else [])
        return lines
    return None


_FAULT_FUNCS = {"missing_country": fault_missing_country, "too_many_lines": fault_too_many_lines,
                "town_in_line": fault_town_in_line}


def apply_fault(record: dict, rng: random.Random) -> tuple[str | None, list[str]]:
    """(fault, lines): a fault chosen at random that applies to this address, or (None, the original lines)."""
    for fault in rng.sample(FAULTS, len(FAULTS)):
        lines = _FAULT_FUNCS[fault](record)
        if lines is not None and lines != record["raw_lines"]:
            return fault, lines
    return None, list(record["raw_lines"])


# ---- XML ------------------------------------------------------------------------------------------------------

def _el(parent, tag, text=None, **attrs):
    child = etree.SubElement(parent, f"{{{parent.nsmap[None]}}}{tag}", **attrs)
    if text is not None:
        child.text = text
    return child


def _party(parent, role: str, name: str, lines: list[str]):
    party = _el(parent, role)
    _el(party, "Nm", name)
    adr = _el(party, "PstlAdr")
    for line in lines:
        _el(adr, "AdrLine", line)
    return party


def _agent(parent, role: str, country: str):
    agent = _el(parent, role)
    _el(_el(agent, "FinInstnId"), "BICFI", f"TEST{country}2LXXX")


def _company(rng: random.Random, country: str) -> str:
    return f"{rng.choice(_NAME_A)} {rng.choice(_NAME_B)} {_FORM[country]}"


def build_message(kind: str, number: int, jobs: list[dict], rng: random.Random) -> bytes:
    """One message of `kind` ('pacs.008' or 'pain.001') with a debtor job and a creditor job.

    Each job is {'country': ..., 'lines': [...]}. Returns UTF-8 XML bytes.
    """
    debtor, creditor = jobs
    ns = _NS[kind]
    prefix = _PREFIX[kind].upper()
    amount = f"{rng.randint(100, 900000) / 100:.2f}"
    currency = _CURRENCY[debtor["country"]]
    root = etree.Element(f"{{{ns}}}Document", nsmap={None: ns})
    if kind == PACS008:
        msg = _el(root, "FIToFICstmrCdtTrf")
        hdr = _el(msg, "GrpHdr")
        _el(hdr, "MsgId", f"SYNTH-{prefix}-{number:04d}")
        _el(hdr, "CreDtTm", "2026-10-12T09:30:00Z")
        _el(hdr, "NbOfTxs", "1")
        _el(_el(hdr, "SttlmInf"), "SttlmMtd", "INDA")
        tx = _el(msg, "CdtTrfTxInf")
        _el(_el(tx, "PmtId"), "EndToEndId", f"SYNTH-E2E-{number:04d}")
        _el(tx, "IntrBkSttlmAmt", amount, Ccy=currency)
        _el(tx, "ChrgBr", "SHAR")
        _party(tx, "Dbtr", _company(rng, debtor["country"]), debtor["lines"])
        _agent(tx, "DbtrAgt", debtor["country"])
        _agent(tx, "CdtrAgt", creditor["country"])
        _party(tx, "Cdtr", _company(rng, creditor["country"]), creditor["lines"])
    else:
        msg = _el(root, "CstmrCdtTrfInitn")
        hdr = _el(msg, "GrpHdr")
        _el(hdr, "MsgId", f"SYNTH-{prefix}-{number:04d}")
        _el(hdr, "CreDtTm", "2026-10-13T08:00:00Z")
        _el(hdr, "NbOfTxs", "1")
        _el(_el(hdr, "InitgPty"), "Nm", _company(rng, debtor["country"]))
        pmt = _el(msg, "PmtInf")
        _el(pmt, "PmtInfId", f"SYNTH-PMT-{number:04d}")
        _el(pmt, "PmtMtd", "TRF")
        _el(_el(pmt, "ReqdExctnDt"), "Dt", "2026-10-14")
        _party(pmt, "Dbtr", _company(rng, debtor["country"]), debtor["lines"])
        _el(_el(_el(_el(pmt, "DbtrAcct"), "Id"), "Othr"), "Id", f"SYNTH-ACCT-{number:04d}")
        _agent(pmt, "DbtrAgt", debtor["country"])
        tx = _el(pmt, "CdtTrfTxInf")
        _el(_el(tx, "PmtId"), "EndToEndId", f"SYNTH-E2E-{number:04d}")
        _el(_el(tx, "Amt"), "InstdAmt", amount, Ccy=currency)
        _agent(tx, "CdtrAgt", creditor["country"])
        _party(tx, "Cdtr", _company(rng, creditor["country"]), creditor["lines"])
        _el(_el(_el(_el(tx, "CdtrAcct"), "Id"), "Othr"), "Id", f"SYNTH-ACCT-{number + 5000:04d}")
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


@lru_cache(maxsize=None)
def _schema(kind: str) -> etree.XMLSchema:
    return etree.XMLSchema(etree.parse(str(_XSD[kind])))


def validate_xml(kind: str, xml: bytes) -> list[str]:
    """XSD errors for the message; an empty list means it validates."""
    schema = _schema(kind)
    schema.validate(etree.fromstring(xml))
    return [f"line {e.line}: {e.message}" for e in schema.error_log]


def xml_path(element) -> str:
    """The Phase 1 job path: an index on every step except the root, e.g. /Document/FIToFICstmrCdtTrf[1]/..."""
    parts = []
    while element is not None:
        tag = etree.QName(element).localname
        parent = element.getparent()
        if parent is None:
            parts.append(tag)
        else:
            same = [c for c in parent if isinstance(c.tag, str) and etree.QName(c).localname == tag]
            parts.append(f"{tag}[{same.index(element) + 1}]")
        element = parent
    return "/" + "/".join(reversed(parts))


def read_jobs(xml: bytes) -> list[tuple[str, str, list[str]]]:
    """(role, xml path, AdrLine texts) of every party address in the message, in document order."""
    root = etree.fromstring(xml)
    out = []
    for adr in root.iter("{*}PstlAdr"):
        role = etree.QName(adr.getparent()).localname
        out.append((role, xml_path(adr), [a.text for a in adr.findall("{*}AdrLine")]))
    return out


# ---- the sample set -------------------------------------------------------------------------------------------

@dataclass
class BuiltMessage:
    filename: str
    xml: bytes
    manifest: dict


def build_messages(records: list[dict], seed: int, count: int = 300) -> list[BuiltMessage]:
    """`count` messages of two jobs each, drawn without repeats from `records` in a seeded random order.

    Messages alternate pacs.008 and pain.001. Roughly FAULT_RATE of the jobs get one message-level fault.
    """
    if 2 * count > len(records):
        raise ValueError(f"{count} messages need {2 * count} addresses, only {len(records)} given")
    order = random.Random(f"{seed}|messages").sample(records, 2 * count)
    out = []
    for n in range(count):
        kind = PACS008 if n % 2 == 0 else PAIN001
        rng = random.Random(f"{seed}|message|{n}")
        pair = order[2 * n:2 * n + 2]
        sent = []
        for record in pair:
            fault, lines = apply_fault(record, rng) if rng.random() < FAULT_RATE else (None, list(record["raw_lines"]))
            sent.append({"record": record, "fault": fault, "lines": lines, "country": record["country"]})
        xml = build_message(kind, n + 1, sent, rng)
        errors = validate_xml(kind, xml)
        filename = f"{_PREFIX[kind]}-{n + 1:04d}.xml"
        paths = read_jobs(xml)
        jobs = []
        for job, (role, path, lines) in zip(sent, paths):
            record = job["record"]
            if lines != job["lines"]:
                raise RuntimeError(f"{filename}: the XML does not round-trip the address lines")
            entry = {
                "role": role, "xml_path": path, "record_id": record["id"], "country": record["country"],
                "difficulty": record["difficulty"], "tags": record["tags"], "raw_lines": lines,
                "gold": record["gold"], "country_hint": record["country"], "fault": job["fault"],
            }
            jobs.append(entry)
        expects_invalid = any(j["fault"] == "too_many_lines" for j in jobs)
        if bool(errors) != expects_invalid:
            raise RuntimeError(f"{filename}: XSD validity {not errors} does not match the faults injected: {errors[:2]}")
        out.append(BuiltMessage(filename, xml, {
            "file": filename, "message_type": kind, "xsd_valid": not errors,
            "xsd_errors": errors[:3], "jobs": jobs,
        }))
    return out


def write_messages(out_dir, messages: list[BuiltMessage], seed: int, source: str) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.xml"):
        old.unlink()
    for m in messages:
        (out / m.filename).write_bytes(m.xml)
    faults = {f: sum(1 for m in messages for j in m.manifest["jobs"] if j["fault"] == f) for f in FAULTS}
    manifest = {
        "seed": seed, "source_split": source, "messages": len(messages),
        "jobs": sum(len(m.manifest["jobs"]) for m in messages), "faults": faults,
        "xsd_valid": sum(1 for m in messages if m.manifest["xsd_valid"]),
        "note": "country_hint is the country letters of the party's bank BIC (always present). "
                "A too_many_lines fault makes the message XSD-invalid on purpose (AdrLine maxOccurs is 7).",
        "files": [m.manifest for m in messages],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest
