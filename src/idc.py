from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
import re


IIN = {
    "604426": ("Prince Edward Island", "Canada"),
    "604427": ("American Samoa", "USA"),
    "604428": ("Quebec", "Canada"),
    "604429": ("Yukon", "Canada"),
    "604430": ("Norther Marianna Islands", "USA"),
    "604431": ("Puerto Rico", "USA"),
    "604432": ("Alberta", "Canada"),
    "604433": ("Nunavut", "Canada"),
    "604434": ("Northwest Territories", "Canada"),
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
    "636012": ("Ontario", "Canada"),
    "636013": ("Nova Scotia", "Canada"),
    "636014": ("California", "USA"),
    "636015": ("Texas", "USA"),
    "636016": ("Newfoundland", "Canada"),
    "636017": ("New Brunswick", "Canada"),
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
    "636028": ("British Columbia", "Canada"),
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
    "636044": ("Saskatchewan", "Canada"),
    "636045": ("Washington", "USA"),
    "636046": ("Kentucky", "USA"),
    "636047": ("Hawaii", "USA"),
    "636048": ("Manitoba", "Canada"),
    "636049": ("Nevada", "USA"),
    "636050": ("Idaho", "USA"),
    "636051": ("Mississippi", "USA"),
    "636052": ("Rhode Island", "USA"),
    "636053": ("Tennessee", "USA"),
    "636054": ("Nebraska", "USA"),
    "636055": ("Georgia", "USA"),
    "636056": ("Coahuila", "Mexico"),
    "636057": ("Hidalgo", "Mexico"),
    "636058": ("Oklahoma", "USA"),
    "636059": ("Alaska", "USA"),
    "636060": ("Wyoming", "USA"),
    "636061": ("West Virginia", "USA"),
    "636062": ("Virgin Islands", "USA"),
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
}

HEADER_RE = re.compile(
    r"(?:@)?ANSI\s*(?P<iin>\d{6})(?P<aamva>\d{2})(?P<jur>\d{2})(?P<cnt>\d{2})?"
)
SUBFILE_START_RE = re.compile(r"(DL|ID)(?=[A-Z]{3})")

MANDATORY = ("DAQ", "DCS", "DBB")  # license#, last name, DOB


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


def _normalize(raw: bytes) -> str:
    t = raw.decode("utf-8", "ignore")
    if "ANSI" not in t.upper():
        t = raw.decode("latin-1", "ignore")
    return t.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")


def _parse_header(text: str) -> tuple[dict[str, int] | None, int, list[str]]:
    m = HEADER_RE.search(text[:256])
    if not m:
        return None, 0, ["Malformed or missing header"]
    hdr = {
        "iin": int(m.group("iin")),
        "aamva": int(m.group("aamva")),
        "jur": int(m.group("jur")),
        "cnt": int(m.group("cnt")) if m.group("cnt") else None,
    }
    cursor = m.end()
    tail = text[cursor:]
    mm = SUBFILE_START_RE.search(tail)
    if mm:
        cursor += mm.start()
    errs = []
    if not (0 <= hdr["aamva"] <= 99):
        errs.append("AAMVA version out of range")
    if not (0 <= hdr["jur"] <= 99):
        errs.append("Jurisdiction version out of range")
    return hdr, cursor, errs


def _parse_fields(text: str, start_idx: int) -> dict[str, str]:
    body = text[start_idx:].replace("\x1e", "\n")
    out: dict[str, str] = {}
    for part in (p for p in re.split(r"\n+", body) if p):
        if len(part) >= 5 and part[:2].isalpha() and part[2:5].isalpha():
            sub, key, val = part[:2], part[2:5], part[5:].strip()
            if sub in ("DL", "ID") or sub.startswith("Z"):
                out.setdefault(key, val)
                continue
        if len(part) >= 3 and part[:3].isalpha():
            out.setdefault(part[:3], part[3:].strip())
    return out


def parse_aamva(raw: bytes) -> Parsed:
    text = _normalize(raw)
    hdr, idx, herrs = _parse_header(text)
    fields = _parse_fields(text, idx) if hdr else {}
    p = Parsed(
        ok=False,
        errors=list(herrs),
        fields=fields,
    )
    if hdr:
        p.iin = str(hdr["iin"]).zfill(6)
        p.aamva_version = hdr["aamva"]
        p.jur_version = hdr["jur"]
        if p.iin in IIN:
            p.issuer, p.country = IIN[p.iin]
        else:
            p.errors.append(f"Unknown IIN: {p.iin}")
    for k in MANDATORY:
        if not fields.get(k):
            p.errors.append(f"Missing field {k}")
    # DOB basic sanity
    dob_raw = fields.get("DBB", "")
    if dob_raw and not re.fullmatch(r"\d{8}", re.sub(r"\D", "", dob_raw)):
        p.errors.append("DBB not 8 digits")
    p.ok = len(p.errors) == 0
    return p


def _parse_date_ymd8(s: str) -> date | None:
    digits = re.sub(r"\D", "", s or "")
    if len(digits) != 8:
        return None
    # try MMDDYYYY first
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
    abbr = (f.get("DAJ") or "").strip().upper()  # state
    if abbr:
        return abbr
    # sometimes DCG holds country, DAJ should be state
    return None


def id21_check(raw: bytes, today: date = None) -> Decision:
    today = today or date.today()
    p = parse_aamva(raw)

    inconsistencies: list[str] = []

    # DOB / age
    dob = _parse_date_ymd8(p.fields.get("DBB", ""))
    age = _compute_age(dob, today) if dob else None
    if dob is None:
        inconsistencies.append("DOB unparsable")
    elif age is not None and age < 21:
        # hard fail
        return Decision(False, True, True, age, ["Under 21"], p)

    # Expiration
    exp = _parse_date_ymd8(p.fields.get("DBA", ""))
    if exp and exp < today:
        inconsistencies.append("Card expired")

    # IIN / state mismatch
    if p.iin and p.iin in IIN and p.country == "US":
        issuer_full = IIN[p.iin][0]
        issuer_abbr = US_ABBR.get(issuer_full)
        state_abbr = _state_abbr_from_fields(p.fields)
        if issuer_abbr and state_abbr and issuer_abbr != state_abbr:
            inconsistencies.append(
                f"State mismatch: IIN={issuer_abbr}, DAJ={state_abbr}"
            )

    # Missing fields
    for k in ("DAQ", "DCS"):
        if not p.fields.get(k):
            inconsistencies.append(f"Missing {k}")

    if p.iin and p.iin not in IIN:
        inconsistencies.append("Unknown IIN")

    approved = age is not None and age >= 21
    needs_review = approved and (len(inconsistencies) > 0 or not p.ok)

    return Decision(approved, needs_review, False, age, inconsistencies, p)


def summarize_for_popup(dec: Decision) -> str:
    f = dec.parsed.fields
    name = f.get("DAC", "") + " " + f.get("DCS", "")
    name = " ".join(name.split())
    issuer = f"{dec.parsed.issuer or 'Unknown'} ({dec.parsed.iin or 'n/a'})"
    dob = f.get("DBB", "")
    exp = f.get("DBA", "")
    lic = f.get("DAQ", "")
    addr = ", ".join(
        x for x in [f.get("DAG", ""), f.get("DAI", ""), f.get("DAJ", "")] if x
    )
    lines = [
        f"Name: {name or 'n/a'}",
        f"License #: {lic or 'n/a'}",
        f"DOB: {dob or 'n/a'}  Age: {dec.age_years if dec.age_years is not None else 'n/a'}",
        f"Expires: {exp or 'n/a'}",
        f"Issuer: {issuer}",
        f"Address: {addr or 'n/a'}",
    ]
    if dec.inconsistencies:
        lines.append("")
        lines.append("Inconsistencies:")
        for s in dec.inconsistencies:
            lines.append(f"- {s}")
    return "\n".join(lines)
