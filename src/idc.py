from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import re


US_IIN = {
    "604427": ("American Samoa", "USA"),
    "604430": ("Northern Mariana Islands", "USA"),
    "604431": ("Puerto Rico", "USA"),
    "636000": ("Virginia", "USA"),
    "636001": ("New York", "USA"),
    "636002": ("Massachusetts", "USA"),
    "636003": ("Maryland", "USA"),
    "636004": ("North Carolina", "USA"),
    "636005": ("South Carolina", "USA"),
    "636006": ("Connecticut", "USA"),
    "636007": ("Louisiana", "USA"),
    "636008": ("Montana", "USA"),
    "636009": ("New Mexico", "USA"),
    "636010": ("Florida", "USA"),
    "636011": ("Delaware", "USA"),
    "636014": ("California", "USA"),
    "636015": ("Texas", "USA"),
    "636018": ("Iowa", "USA"),
    "636019": ("Guam", "USA"),
    "636020": ("Colorado", "USA"),
    "636021": ("Arkansas", "USA"),
    "636022": ("Kansas", "USA"),
    "636023": ("Ohio", "USA"),
    "636024": ("Vermont", "USA"),
    "636025": ("Pennsylvania", "USA"),
    "636026": ("Arizona", "USA"),
    "636027": ("State Dept. (Diplomatic)", "USA"),
    "636029": ("Oregon", "USA"),
    "636030": ("Missouri", "USA"),
    "636031": ("Wisconsin", "USA"),
    "636032": ("Michigan", "USA"),
    "636033": ("Alabama", "USA"),
    "636034": ("North Dakota", "USA"),
    "636035": ("Illinois", "USA"),
    "636036": ("New Jersey", "USA"),
    "636037": ("Indiana", "USA"),
    "636038": ("Minnesota", "USA"),
    "636039": ("New Hampshire", "USA"),
    "636040": ("Utah", "USA"),
    "636041": ("Maine", "USA"),
    "636042": ("South Dakota", "USA"),
    "636043": ("District of Columbia", "USA"),
    "636045": ("Washington", "USA"),
    "636046": ("Kentucky", "USA"),
    "636047": ("Hawaii", "USA"),
    "636049": ("Nevada", "USA"),
    "636050": ("Idaho", "USA"),
    "636051": ("Mississippi", "USA"),
    "636052": ("Rhode Island", "USA"),
    "636053": ("Tennessee", "USA"),
    "636054": ("Nebraska", "USA"),
    "636055": ("Georgia", "USA"),
    "636058": ("Oklahoma", "USA"),
    "636059": ("Alaska", "USA"),
    "636060": ("Wyoming", "USA"),
    "636061": ("West Virginia", "USA"),
    "636062": ("U.S. Virgin Islands", "USA"),
}

US_ABBR = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "District of Columbia": "DC",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
    "Puerto Rico": "PR",
    "Guam": "GU",
    "U.S. Virgin Islands": "VI",
    "American Samoa": "AS",
    "Northern Mariana Islands": "MP",
}

MANDATORY = ("DAQ", "DCS", "DBB")

_CTRL_RS = 0x1E
_CTRL_CR = 0x0D
_CTRL_GS = 0x1D

_AAMVA_START = b"@\n" + bytes([_CTRL_RS]) + b"\rANSI "
_ANSI = b"ANSI "


@dataclass
class Parsed:
    ok: bool
    errors: list[str] = field(default_factory=list)
    iin: str | None = None
    issuer: str | None = None
    country: str | None = None
    aamva_version: int | None = None
    jur_version: int | None = None
    fields: dict[str, str] = field(default_factory=dict)


@dataclass
class Decision:
    approved_21: bool
    needs_review: bool
    hard_fail: bool
    age_years: int | None
    inconsistencies: list[str] = field(default_factory=list)
    parsed: Parsed = field(default_factory=lambda: Parsed(ok=False))


def _find_aamva_start(raw: bytes) -> int | None:
    i = raw.find(_AAMVA_START)
    if i != -1:
        return i
    j = raw.find(_ANSI)
    if j == -1:
        return None
    if j >= 4 and raw[j - 4 : j] == b"@\n" + bytes([_CTRL_RS]) + b"\r":
        return j - 4
    return j


def _strip_trailing_pad(b: bytes) -> bytes:
    return b.rstrip(b" \x00\t")


def _read_ascii_digits(raw: bytes, pos: int, n: int) -> tuple[str | None, int]:
    b = raw[pos : pos + n]
    if len(b) != n:
        return None, pos + len(b)
    if not b.isdigit():
        return None, pos + n
    return b.decode("ascii"), pos + n


def _parse_header_and_subfiles(raw: bytes) -> tuple[dict[str, int | str] | None, dict[str, bytes], list[str], int]:
    errs: list[str] = []
    subfiles: dict[str, bytes] = {}

    start = _find_aamva_start(raw)
    if start is None:
        return None, subfiles, ["Malformed or missing ANSI header"], 0

    if raw[start : start + 4] != b"@\n" + bytes([_CTRL_RS]) + b"\r":
        errs.append("Missing or nonstandard @/LF/RS/CR prefix")

    if raw[start + 4 : start + 9] != _ANSI:
        errs.append("Missing file type 'ANSI '")

    pos = start + 9

    iin_s, pos = _read_ascii_digits(raw, pos, 6)
    aamva_s, pos = _read_ascii_digits(raw, pos, 2)
    jur_s, pos = _read_ascii_digits(raw, pos, 2)
    ent_s, pos = _read_ascii_digits(raw, pos, 2)

    if iin_s is None:
        errs.append("IIN not 6 digits")
    if aamva_s is None:
        errs.append("AAMVA version not numeric")
    if jur_s is None:
        errs.append("Jurisdiction version not numeric")
    if ent_s is None:
        errs.append("Number of entries not numeric")

    aamva = int(aamva_s) if aamva_s is not None else None
    jur = int(jur_s) if jur_s is not None else None
    ent = int(ent_s) if ent_s is not None else None

    if ent is not None and not (1 <= ent <= 99):
        errs.append("Number of entries out of range")

    designators: list[tuple[str, int, int]] = []
    if ent is not None:
        need = ent * 10
        if pos + need > len(raw):
            errs.append("Truncated subfile designator table")
        else:
            for _ in range(ent):
                st = raw[pos : pos + 2]
                off = raw[pos + 2 : pos + 6]
                ln = raw[pos + 6 : pos + 10]
                pos += 10

                st_s = st.decode("ascii", "ignore")
                off_s = off.decode("ascii", "ignore")
                ln_s = ln.decode("ascii", "ignore")

                if len(st_s) != 2 or not st_s.isalnum() or not st_s.isupper():
                    errs.append(f"Bad subfile type '{st_s}'")
                    continue
                if not (off_s.isdigit() and ln_s.isdigit()):
                    errs.append(f"Bad offset/length for {st_s}")
                    continue

                designators.append((st_s, int(off_s), int(ln_s)))

    for st_s, off_i, ln_i in designators:
        a = start + off_i
        b = a + ln_i
        if a < start or b > len(raw) or ln_i <= 0:
            errs.append(f"Subfile {st_s} out of bounds (off={off_i} len={ln_i})")
            continue
        chunk = raw[a:b]
        if not chunk.startswith(st_s.encode("ascii", "ignore")):
            errs.append(f"Subfile {st_s} does not start with its type code")
        stripped = _strip_trailing_pad(chunk)
        if not stripped.endswith(b"\r"):
            errs.append(f"Subfile {st_s} missing CR segment terminator")
        subfiles[st_s] = chunk

    hdr = {
        "start": start,
        "iin": iin_s or "",
        "aamva": aamva if aamva is not None else -1,
        "jur": jur if jur is not None else -1,
        "entries": ent if ent is not None else -1,
    }
    return hdr, subfiles, errs, pos


def _best_effort_text(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1", "ignore")


def _parse_fields_from_subfile_bytes(sub: bytes) -> tuple[dict[str, str], list[str]]:
    errs: list[str] = []
    if len(sub) < 2:
        return {}, ["Empty subfile"]

    body = sub[2:]
    body = body.replace(bytes([_CTRL_RS]), b"\n").replace(bytes([_CTRL_GS]), b"\n").replace(b"\r", b"\n")
    text = _best_effort_text(body)

    out: dict[str, str] = {}
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue

        if len(line) >= 5 and line[:2] in ("DL", "ID", "EN") and line[2:5].isalnum():
            key = line[2:5]
            val = line[5:].strip()
        elif len(line) >= 3 and line[:3].isalnum() and line[:3].isupper():
            key = line[:3]
            val = line[3:].strip()
        else:
            continue

        prev = out.get(key)
        if prev is None:
            out[key] = val
        elif prev != val:
            errs.append(f"Conflicting {key} values")
    return out, errs


def _parse_fields_fallback(text: str) -> dict[str, str]:
    t = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    t = t.replace("\x1e", "\n").replace("\x1d", "\n")
    out: dict[str, str] = {}

    for part in (p for p in re.split(r"\n+", t) if p):
        part = part.strip()
        if not part:
            continue
        if len(part) >= 5 and part[:2] in ("DL", "ID", "EN") and part[2:5].isalnum():
            key = part[2:5]
            val = part[5:].strip()
            out.setdefault(key, val)
            continue
        if len(part) >= 3 and part[:3].isalnum() and part[:3].isupper():
            out.setdefault(part[:3], part[3:].strip())
    return out


def _is_effectively_missing(v: str | None) -> bool:
    if v is None:
        return True
    s = v.strip()
    if not s:
        return True
    u = s.upper()
    return u in ("NONE", "UNAVL", "UNAVL.")


def parse_aamva(raw: bytes) -> Parsed:
    hdr, subfiles, errs, _ = _parse_header_and_subfiles(raw)

    fields: dict[str, str] = {}
    if subfiles:
        primary_key = "DL" if "DL" in subfiles else ("ID" if "ID" in subfiles else ("EN" if "EN" in subfiles else ""))
        if primary_key:
            fields, ferrs = _parse_fields_from_subfile_bytes(subfiles[primary_key])
            errs.extend(ferrs)
        else:
            errs.append("No DL/ID/EN subfile found")
    else:
        text = _best_effort_text(raw)
        fields = _parse_fields_fallback(text)
        errs.append("Parsed without subfile table (fallback)")

    p = Parsed(ok=False, errors=list(errs), fields=fields)

    if hdr:
        iin = str(hdr.get("iin", "")).zfill(6) if hdr.get("iin") else None
        p.iin = iin
        p.aamva_version = int(hdr["aamva"]) if isinstance(hdr.get("aamva"), int) and hdr["aamva"] >= 0 else None
        p.jur_version = int(hdr["jur"]) if isinstance(hdr.get("jur"), int) and hdr["jur"] >= 0 else None
        if iin and iin in US_IIN:
            p.issuer, p.country = US_IIN[iin]

    for k in MANDATORY:
        if _is_effectively_missing(fields.get(k)):
            p.errors.append(f"Missing field {k}")

    dob_raw = fields.get("DBB", "")
    if not _is_effectively_missing(dob_raw):
        digits = re.sub(r"\D", "", dob_raw)
        if len(digits) != 8:
            p.errors.append("DBB not 8 digits")

    p.ok = len(p.errors) == 0
    return p


def _parse_date_ymd8(s: str) -> date | None:
    digits = re.sub(r"\D", "", s or "")
    if len(digits) != 8:
        return None

    mm, dd, yyyy = int(digits[:2]), int(digits[2:4]), int(digits[4:8])
    try:
        return date(yyyy, mm, dd)
    except ValueError:
        y, m, d = int(digits[:4]), int(digits[4:6]), int(digits[6:8])
        try:
            return date(y, m, d)
        except ValueError:
            return None


def _compute_age(dob: date, today: date) -> int:
    years = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        years -= 1
    return years


def _state_abbr_from_fields(f: dict[str, str]) -> str | None:
    abbr = (f.get("DAJ") or "").strip().upper()
    return abbr or None


def id21_check(raw: bytes, today: date = None) -> Decision:
    today = today or date.today()
    p = parse_aamva(raw)
    f = p.fields

    inconsistencies: list[str] = []

    dob = _parse_date_ymd8(f.get("DBB", ""))
    age = _compute_age(dob, today) if dob else None

    if dob is None:
        inconsistencies.append("DOB unparsable")
    else:
        if age is not None and (age < 0 or age > 120):
            inconsistencies.append("DOB produces implausible age")
        if age is not None and age < 21:
            return Decision(False, True, True, age, ["Under 21"], p)

    exp = _parse_date_ymd8(f.get("DBA", ""))
    iss = _parse_date_ymd8(f.get("DBD", ""))

    if exp and exp < today:
        inconsistencies.append("Card expired")
    if iss and iss > today:
        inconsistencies.append("Issue date in the future")
    if exp and iss and exp < iss:
        inconsistencies.append("Expiration before issue date")

    if not _is_effectively_missing(f.get("DCF")) is False:
        pass
    if _is_effectively_missing(f.get("DCF")):
        inconsistencies.append("Missing DCF (document discriminator)")
    if _is_effectively_missing(f.get("DCK")):
        inconsistencies.append("Missing DCK (inventory control number)")

    dcg = (f.get("DCG") or "").strip().upper()
    if dcg and not re.fullmatch(r"[A-Z]{3}", dcg):
        inconsistencies.append("DCG not 3-letter country code")

    if p.iin and p.iin in US_IIN:
        issuer_full = US_IIN[p.iin][0]
        issuer_abbr = US_ABBR.get(issuer_full)
        state_abbr = _state_abbr_from_fields(f)
        if issuer_abbr and state_abbr and issuer_abbr != state_abbr:
            inconsistencies.append(f"State mismatch: IIN={issuer_abbr}, DAJ={state_abbr}")

    if p.iin and p.iin not in US_IIN:
        inconsistencies.append("Unknown IIN (not mapped)")

    dak = re.sub(r"\D", "", f.get("DAK", "") or "")
    if dak and len(dak) not in (5, 9):
        inconsistencies.append("Postal code length unusual")

    for k in ("DAQ", "DCS"):
        if _is_effectively_missing(f.get(k)):
            inconsistencies.append(f"Missing {k}")

    approved = age is not None and age >= 21
    needs_review = approved and (len(inconsistencies) > 0 or not p.ok)

    return Decision(approved, needs_review, False, age, inconsistencies, p)


def summarize_for_popup(dec: Decision) -> str:
    f = dec.parsed.fields

    name = (f.get("DAC", "") + " " + f.get("DCS", "")).strip()
    name = " ".join(name.split())

    lic = (f.get("DAQ") or "").strip()
    dob = (f.get("DBB") or "").strip()
    exp = (f.get("DBA") or "").strip()

    dcg = (f.get("DCG") or "").strip()
    dda = (f.get("DDA") or "").strip()

    issuer_name = dec.parsed.issuer or "Unknown"
    iin = dec.parsed.iin or "n/a"
    ver = (
        f"AAMVA {dec.parsed.aamva_version if dec.parsed.aamva_version is not None else 'n/a'}"
        f", JUR {dec.parsed.jur_version if dec.parsed.jur_version is not None else 'n/a'}"
    )

    addr = ", ".join(x for x in [f.get("DAG", ""), f.get("DAI", ""), f.get("DAJ", ""), f.get("DAK", "")] if x)
    addr = " ".join(addr.split())

    lines = [
        f"Name: {name or 'n/a'}",
        f"License #: {lic or 'n/a'}",
        f"DOB: {dob or 'n/a'}  Age: {dec.age_years if dec.age_years is not None else 'n/a'}",
        f"Expires: {exp or 'n/a'}",
        f"Issuer: {issuer_name} (IIN {iin})",
        f"{ver}",
        f"DCG: {dcg or 'n/a'}  DDA: {dda or 'n/a'}",
        f"Address: {addr or 'n/a'}",
    ]

    if dec.inconsistencies or dec.parsed.errors:
        lines.append("")
        lines.append("Flags:")
        for s in dec.inconsistencies:
            lines.append(f"- {s}")
        for e in dec.parsed.errors:
            if e not in dec.inconsistencies:
                lines.append(f"- {e}")

    return "\n".join(lines)
