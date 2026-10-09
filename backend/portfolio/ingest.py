"""Read an uploaded exposure file. A failure still returns sample locations."""

import csv
import re
import tempfile
from pathlib import Path

from .copilot import CopilotError, ask_ollama, configured, parse_agent

MAX_BYTES = 8 * 1024 * 1024
ROW_LIMIT = 12
SUMMARY_TIMEOUT = 20
ALLOWED = {".csv", ".xls", ".xlsx", ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif"}

SAMPLE_ROWS = (
    {
        "loc_id": "SAMPLE-01",
        "lat": -1.2864,
        "lon": 36.8172,
        "housing_class": "permanent_masonry",
        "tiv_kes": 18500000,
        "source": "sample",
    },
    {
        "loc_id": "SAMPLE-02",
        "lat": -1.3197,
        "lon": 36.9256,
        "housing_class": "semi_permanent",
        "tiv_kes": 3200000,
        "source": "sample",
    },
    {
        "loc_id": "SAMPLE-03",
        "lat": -1.2833,
        "lon": 36.7167,
        "housing_class": "informal_iron_sheet",
        "tiv_kes": 740000,
        "source": "sample",
    },
    {
        "loc_id": "SAMPLE-04",
        "lat": -1.3031,
        "lon": 36.8900,
        "housing_class": "concrete_rcc",
        "tiv_kes": 42000000,
        "source": "sample",
    },
)

_ALIASES = {
    "lat": ("lat", "latitude"),
    "lon": ("lon", "lng", "long", "longitude"),
    "loc_id": ("locid", "locationid", "buildingid", "id"),
    "tiv_kes": ("tivkes", "tiv", "tsi", "suminsured", "insuredvalue"),
    "housing_class": ("housingclass", "housetype", "construction", "class"),
}


def ingest_upload(upload):
    """Return locations from the file, or sample Nairobi locations when it cannot be read."""
    filename = _clean_name(getattr(upload, "name", "") or "upload")
    suffix = Path(filename).suffix.lower()
    kind = _kind(suffix)
    if suffix not in ALLOWED or getattr(upload, "size", 0) > MAX_BYTES:
        return _sample(filename, kind or "file")

    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / filename
        with path.open("wb") as handle:
            for chunk in upload.chunks():
                handle.write(chunk)
        rows = _rows_from_path(path, suffix)
        excerpt = _pdf_excerpt(path) if suffix == ".pdf" else ""
        if suffix == ".pdf" and not rows:
            rows = _rows_from_text(excerpt)

    if rows:
        summary = _summary(filename, kind, rows, excerpt)
        return _payload(filename, kind, "ingested", summary, rows)
    return _sample(filename, kind, excerpt)


def _sample(filename, kind, excerpt=""):
    summary = _summary(filename, kind, [], excerpt)
    if "sample" not in summary.lower():
        summary = summary.rstrip(".") + ". Sample Nairobi locations are shown."
    return _payload(filename, kind, "sample", summary, [dict(row) for row in SAMPLE_ROWS])


def _payload(filename, kind, status, summary, rows):
    located = any(row.get("lat") is not None and row.get("lon") is not None for row in rows)
    return {
        "filename": filename,
        "kind": kind,
        "status": status,
        "summary": summary,
        "page": "map" if located else "exposure",
        "rows": rows[:ROW_LIMIT],
    }


def _summary(filename, kind, rows, excerpt):
    count = len(rows)
    fallback = (
        f"Read {count} location{'s' if count != 1 else ''} from {filename}."
        if count
        else f"{filename} could not be read as exposure, so sample Nairobi locations are shown."
    )
    if not configured():
        return fallback
    preview = [
        {
            "loc_id": row["loc_id"],
            "lat": row["lat"],
            "lon": row["lon"],
            "housing_class": row["housing_class"],
            "tiv_kes": row["tiv_kes"],
        }
        for row in rows[:4]
    ]
    prompt = (
        "Summarize this exposure upload for a Nairobi flood prototype in one sentence. "
        "Use only the facts below. Do not invent buildings or amounts.\n"
        f"File: {filename}\nKind: {kind}\nLocations: {count}\nRows: {preview}\n"
        f"Excerpt: {excerpt[:1500]}"
    )
    try:
        spoken, _actions = parse_agent(ask_ollama([{"role": "user", "content": prompt}], timeout=SUMMARY_TIMEOUT))
    except CopilotError:
        return fallback
    spoken = " ".join(spoken.split())
    if not spoken or len(spoken) > 400:
        return fallback
    return spoken


def _rows_from_path(path, suffix):
    try:
        if suffix == ".csv":
            records = _read_csv(path)
        elif suffix in {".xls", ".xlsx"}:
            records = _read_excel(path)
        else:
            return []
        return _map_records(records)
    except Exception:
        return []


def _read_csv(path):
    last_error = None
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            with path.open(newline="", encoding=encoding) as handle:
                return list(csv.DictReader(handle))
        except UnicodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    return []


def _read_excel(path):
    import pandas as pd

    frame = pd.read_excel(path)
    return frame.to_dict(orient="records")


def _pdf_excerpt(path):
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    try:
        reader = PdfReader(str(path))
        parts = []
        for page in list(reader.pages)[:3]:
            parts.append(page.extract_text() or "")
        return "\n".join(parts)[:4000]
    except Exception:
        return ""


def _rows_from_text(text):
    found = re.findall(r"(-1\.\d{3,})\s*[, ]\s*(36\.\d{3,})", text or "")
    rows = []
    for index, (lat, lon) in enumerate(found[:ROW_LIMIT], start=1):
        rows.append(_row(f"DOC-{index:02d}", float(lat), float(lon), "unspecified", None, "file"))
    return rows


def _map_records(records):
    rows = []
    seen = set()
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            continue
        lat = _number(_pick(record, "lat"))
        lon = _number(_pick(record, "lon"))
        if lat is None or lon is None or not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            continue
        loc_id = str(_pick(record, "loc_id") or f"ROW-{index:02d}").strip() or f"ROW-{index:02d}"
        loc_id = loc_id[:40]
        if loc_id in seen:
            loc_id = f"{loc_id}-{index}"
        seen.add(loc_id)
        housing = str(_pick(record, "housing_class") or "unspecified").strip() or "unspecified"
        rows.append(_row(loc_id, lat, lon, housing[:40], _number(_pick(record, "tiv_kes")), "file"))
        if len(rows) >= ROW_LIMIT:
            break
    return rows


def _row(loc_id, lat, lon, housing_class, tiv_kes, source):
    return {
        "loc_id": loc_id,
        "lat": lat,
        "lon": lon,
        "housing_class": housing_class,
        "tiv_kes": tiv_kes,
        "source": source,
    }


def _pick(record, field):
    normalized = {_norm(key): value for key, value in record.items() if key is not None}
    for alias in _ALIASES[field]:
        if alias in normalized and _present(normalized[alias]):
            return normalized[alias]
    return None


def _present(value):
    if value is None:
        return False
    try:
        if value != value:
            return False
    except TypeError:
        pass
    return str(value).strip() != ""


def _number(value):
    if not _present(value):
        return None
    try:
        number = float(str(value).replace(",", "").replace("KES", "").strip())
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _norm(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _clean_name(name):
    base = Path(str(name)).name
    base = re.sub(r"[^\w.\- ]+", "", base).strip() or "upload"
    return base[:80]


def _kind(suffix):
    if suffix == ".csv":
        return "csv"
    if suffix in {".xls", ".xlsx"}:
        return "spreadsheet"
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        return "image"
    return "file"
