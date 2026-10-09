"""Highest-risk brief for the extreme tier. Figures are copied from the engine payload."""

import re
from datetime import datetime, timezone

from .engine import get_payload

TOP_COUNT = 8
CLASS_LABELS = {
    "informal_iron_sheet": "Informal iron sheet",
    "semi_permanent": "Semi-permanent",
    "permanent_masonry": "Permanent masonry",
    "concrete_rcc": "Concrete RCC",
}


def is_risk_brief(message):
    text = " ".join((message or "").lower().split())
    asks_for_risk = re.search(r"\b(highest[-\s]?risk|most at risk)\b", text)
    names_extreme = re.search(r"\bextreme\b", text)
    return bool(asks_for_risk and names_extreme)


def build_brief():
    chosen, event, damage, stats = _selection()
    reply = _explanation(chosen, event, damage, stats)
    return {
        "reply": reply,
        "actions": [
            {"name": "set_scenario", "scenario": "reference"},
            {"name": "set_tier", "tier": "extreme"},
            {"name": "highlight", "ids": [item["loc_id"] for item in chosen]},
        ],
        "review": {
            "required": True,
            "tier": "extreme",
            "assumption": "reference",
            "title": "Approve the extreme-scenario PDF",
            "detail": (
                f"{len(chosen)} buildings are framed on the map. "
                "The PDF is created only after you approve it."
            ),
        },
    }


def render_pdf(approver):
    chosen, event, damage, stats = _selection()
    stamped = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "Dira  Nairobi urban flood risk",
        "Extreme-tier brief  approved for download",
        "",
        "Synthetic portfolio. Susceptibility proxy, not a flood depth.",
        "Return periods are provisional D-004 labels, not measured frequencies.",
        f"Damage assumption: {damage['short_label']} (H={damage['h']}).",
        f"Event: {event['label']}, assumed {event['assumed_return_period_years']}-year.",
        event["note"],
        "",
        f"Portfolio TIV: {_kes(stats['tiv_kes'], 0)}",
        f"Estimated portfolio loss: {_kes(stats['portfolio_loss_kes'])}",
        f"Proxy-flagged buildings: {stats['affected_buildings']}",
        "",
        "Highest estimated loss under this tier",
        "A building is listed because its engine loss is among the largest.",
        "The susceptibility score is a proxy. It is not a modelled flood depth.",
        "",
    ]
    for index, item in enumerate(chosen, start=1):
        lines.append(
            f"{index}. {item['loc_id']}  {_class_label(item['housing_class'])}"
        )
        lines.append(
            f"   TIV {_kes(item['tiv_kes'], 0)}   loss {_kes(item['loss_kes'])}"
        )
        lines.append(
            f"   susceptibility {item['hazard_score']:.4f}   "
            f"damage ratio {item['damage_ratio']:.4f}"
        )
        lines.append("")
    lines.append(f"Approved by {approver} at {stamped}.")
    lines.append("This file was not created until that approval.")
    return _pdf(lines)


def _selection():
    payload = get_payload()
    event = next(item for item in payload["tiers"] if item["id"] == "extreme")
    damage = next(item for item in payload["scenarios"] if item["id"] == "reference")
    stats = payload["tier_summary"]["reference"]["extreme"]
    ranked = []
    for building in payload["buildings"]:
        metric = building["metrics"]["reference"]["extreme"]
        ranked.append(
            {
                "loc_id": building["loc_id"],
                "housing_class": building["housing_class"],
                "tiv_kes": building["tiv_kes"],
                "loss_kes": metric["loss_kes"] or 0,
                "hazard_score": metric["hazard_score"] or 0,
                "damage_ratio": metric["damage_ratio"] or 0,
            }
        )
    ranked.sort(key=lambda item: (item["loss_kes"], item["hazard_score"]), reverse=True)
    positive = [item for item in ranked if item["loss_kes"] > 0]
    chosen = (positive or ranked)[:TOP_COUNT]
    return chosen, event, damage, stats


def _explanation(chosen, event, damage, stats):
    shown = chosen[:5]
    lines = [
        (
            f"The map is on the {event['label']} tier "
            f"(assumed {event['assumed_return_period_years']}-year, {event['note']}) "
            f"with the {damage['short_label']} damage assumption, H={damage['h']}."
        ),
        (
            f"Portfolio loss for this tier is {_kes(stats['portfolio_loss_kes'])}. "
            f"{stats['affected_buildings']} buildings are proxy-flagged."
        ),
        (
            "These buildings are the highest risk in this tier because their estimated loss "
            "is the largest. That loss comes from the susceptibility proxy and the damage "
            "assumption. It is not a measured flood depth."
        ),
    ]
    for item in shown:
        lines.append(
            f"{item['loc_id']} ({_class_label(item['housing_class'])}): "
            f"susceptibility {item['hazard_score']:.4f}, "
            f"damage ratio {item['damage_ratio']:.4f}, "
            f"loss {_kes(item['loss_kes'])}."
        )
    if len(chosen) > len(shown):
        lines.append(f"{len(chosen) - len(shown)} more buildings are included in the PDF.")
    lines.append("Approve the report to download the PDF. It is not created until you do.")
    return " ".join(lines)


def _class_label(value):
    return CLASS_LABELS.get(value, value)


def _kes(value, digits=2):
    return f"KES {float(value):,.{digits}f}"


def _pdf(lines):
    wrapped = []
    for line in lines:
        wrapped.extend(_wrap(line, 90))
    page_size = 42
    pages = [wrapped[index : index + page_size] for index in range(0, len(wrapped), page_size)] or [[""]]
    streams = []
    for page in pages:
        commands = ["BT", "/F1 11 Tf", "14 TL", "48 760 Td"]
        for index, line in enumerate(page):
            if index:
                commands.append("T*")
            commands.append(f"({_escape(line)}) Tj")
        commands.append("ET")
        streams.append("\n".join(commands).encode("latin-1", "replace"))

    objects = []

    def add(body):
        objects.append(body)
        return len(objects)

    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    content_ids = [add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream") for stream in streams]
    page_ids = []
    for content_id in content_ids:
        page_ids.append(
            add(
                b"<< /Type /Page /Parent 0 0 R /MediaBox [0 0 612 792] "
                + f"/Contents {content_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode()
            )
        )
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    pages_id = add(f"<< /Type /Pages /Count {len(page_ids)} /Kids [{kids}] >>".encode())
    for page_id in page_ids:
        objects[page_id - 1] = objects[page_id - 1].replace(b"/Parent 0 0 R", f"/Parent {pages_id} 0 R".encode())
    catalog_id = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode())

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{number} 0 obj\n".encode())
        out.extend(body)
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode())
    out.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )
    return bytes(out)


def _wrap(line, width):
    text = " ".join(str(line).split())
    if not text:
        return [""]
    rows = []
    while len(text) > width:
        cut = text.rfind(" ", 0, width)
        if cut < 1:
            cut = width
        rows.append(text[:cut])
        text = text[cut:].strip()
    rows.append(text)
    return rows


def _escape(text):
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
