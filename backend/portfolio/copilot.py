"""CAT Copilot replies from Ollama. Loss figures are copied from the engine payload."""

import base64
import json
import re
import urllib.error
import urllib.request

from django.conf import settings

from .engine import get_payload

TIMEOUT_SECONDS = 120
HISTORY_LIMIT = 8
TEXT_LIMIT = 2000
PAGES = ("overview", "map", "exposure", "loss", "reports")
PAGE_KEYS = (
    ("reports", ("reports", "report")),
    ("overview", ("overview", "home")),
    ("exposure", ("exposure",)),
    ("loss", ("loss analysis", "loss section")),
    ("map", ("risk map", "the map", "map")),
)


class CopilotError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.message = message
        self.status = status


def configured():
    return bool(
        settings.OLLAMA_BASE_URL
        and settings.OLLAMA_USERNAME
        and settings.OLLAMA_PASSWORD
        and settings.OLLAMA_MODEL
    )


def clean_history(value):
    if not isinstance(value, list):
        return []
    cleaned = []
    for item in value[-HISTORY_LIMIT:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            continue
        text = " ".join(content.split())
        if not text:
            continue
        cleaned.append({"role": role, "content": text[:TEXT_LIMIT]})
    return cleaned


def briefing(tier, assumption, selected_id):
    payload = get_payload()
    tiers = {item["id"]: item for item in payload["tiers"]}
    scenarios = {item["id"]: item for item in payload["scenarios"]}
    if tier not in tiers:
        tier = "common"
    if assumption not in scenarios:
        assumption = "reference"
    event = tiers[tier]
    damage = scenarios[assumption]
    stats = payload["tier_summary"][assumption][tier]
    lines = [
        f"Buildings: {len(payload['buildings'])}.",
        f"Portfolio TIV KES: {stats['tiv_kes']}.",
        (
            f"Current event: {event['label']}, assumed {event['assumed_return_period_years']}-year "
            f"label, AEP {event['annual_exceedance_probability']} ({event['return_period_basis']}). {event['note']}"
        ),
        f"Damage assumption: {damage['short_label']}, H={damage['h']}.",
        f"Portfolio loss KES: {stats['portfolio_loss_kes']}.",
        f"Proxy-flagged buildings: {stats['affected_buildings']}.",
        f"Loss as a share of TIV: {stats['loss_pct_portfolio']}.",
    ]
    for row in payload["class_summary"][assumption][tier]:
        lines.append(
            f"Housing {row['housing_class']}: {row['buildings']} buildings, loss KES {row['loss_kes']}."
        )
    building = next((item for item in payload["buildings"] if item["loc_id"] == selected_id), None)
    if building is not None:
        metric = building["metrics"].get(assumption, {}).get(tier, {})
        lines.append(
            f"Selected {building['loc_id']}, class {building['housing_class']}, "
            f"TIV KES {building['tiv_kes']}, susceptibility {metric.get('hazard_score')}, "
            f"damage ratio {metric.get('damage_ratio')}, loss KES {metric.get('loss_kes')}, "
            f"proxy-flagged {metric.get('affected')}."
        )
    lines.append("Hotspots: " + ", ".join(item["name"] for item in payload["hotspots"]) + ".")
    return "\n".join(lines)


def command_actions(message):
    """Actions implied by the user's words. The model may add more of the same kind."""
    text = " ".join(message.lower().split())
    actions = []
    if re.search(r"\b(go to|open|show|take me|switch to|navigate)\b", text):
        for page, keys in PAGE_KEYS:
            if any(re.search(rf"\b{re.escape(key)}\b", text) for key in keys):
                actions.append({"name": "navigate", "page": page})
                break
    hotspot = _named_hotspot(text)
    if hotspot:
        if not any(item.get("page") == "map" for item in actions):
            actions.append({"name": "navigate", "page": "map"})
        actions.append({"name": "fly_to", "hotspot": hotspot})
    elif re.search(r"\bzoom in(?:to)?\b", text):
        if not any(item.get("page") == "map" for item in actions):
            actions.append({"name": "navigate", "page": "map"})
        actions.append({"name": "zoom_in"})
    elif re.search(r"\bzoom out\b", text):
        if not any(item.get("page") == "map" for item in actions):
            actions.append({"name": "navigate", "page": "map"})
        actions.append({"name": "zoom_out"})
    return actions


def _named_hotspot(text):
    names = [item["name"] for item in get_payload()["hotspots"]]
    for name in sorted(names, key=len, reverse=True):
        if re.search(rf"\b{re.escape(name.lower())}\b", text):
            return name
    return ""


def sanitize_actions(value):
    if not isinstance(value, list):
        return []
    cleaned = []
    for item in value[:6]:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if name == "navigate" and item.get("page") in PAGES:
            cleaned.append({"name": "navigate", "page": item["page"]})
        elif name in {"zoom_in", "zoom_out"}:
            cleaned.append({"name": name})
        elif name == "fly_to" and isinstance(item.get("hotspot"), str) and item["hotspot"].strip():
            cleaned.append({"name": "fly_to", "hotspot": " ".join(item["hotspot"].split())[:80]})
    return cleaned


def merge_actions(*groups):
    merged = []
    seen = set()
    for group in groups:
        for action in group:
            key = json.dumps(action, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            merged.append(action)
    return merged


def parse_agent(text):
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
        candidate = re.sub(r"\s*```$", "", candidate)
    body = _json_object(candidate)
    if isinstance(body, dict) and isinstance(body.get("reply"), str) and body["reply"].strip():
        return body["reply"].strip(), sanitize_actions(body.get("actions"))
    return text.strip(), []


def _json_object(text):
    try:
        body = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            body = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return body if isinstance(body, dict) else None


def reply(message, history, tier, assumption, selected_id):
    if not configured():
        raise CopilotError("The language model is not configured.", status=503)
    system = (
        "You are the CAT Copilot for Dira, a Nairobi urban flood prototype. "
        "Answer only from the figures below. If a figure is not listed, say you do not have it. "
        "The hazard is a susceptibility proxy, not a flood depth or a modelled flood event. "
        "Return-period years are provisional D-004 labels, not measured frequencies. "
        "The portfolio is synthetic and the damage parameter H is an assumption. "
        "Be concise. "
        "When the user asks you to operate the app, reply with one JSON object and no other text: "
        '{"reply":"short confirmation","actions":[{"name":"navigate","page":"reports"}]}. '
        "Allowed actions are navigate with page overview, map, exposure, loss, or reports; "
        "zoom_in; zoom_out; and fly_to with a hotspot name from the list below. "
        "For an ordinary question, actions must be an empty array.\n\n"
        + briefing(tier, assumption, selected_id)
    )
    messages = [{"role": "system", "content": system}, *history, {"role": "user", "content": message}]
    spoken, model_actions = parse_agent(ask_ollama(messages))
    commands = command_actions(message)
    actions = merge_actions(commands, model_actions)
    if commands:
        spoken = _confirmation(actions)
    return spoken, actions


def _confirmation(actions):
    labels = {
        "overview": "Overview",
        "map": "Risk Map",
        "exposure": "Exposure",
        "loss": "Loss Analysis",
        "reports": "Reports",
    }
    parts = []
    for action in actions:
        if action["name"] == "navigate":
            parts.append(f"Opened {labels[action['page']]}.")
        elif action["name"] == "zoom_in":
            parts.append("Zoomed in on the map.")
        elif action["name"] == "zoom_out":
            parts.append("Zoomed out on the map.")
        elif action["name"] == "fly_to":
            parts.append(f"Moved the map to {action['hotspot']}.")
    return " ".join(parts)


def ask_ollama(messages):
    url = settings.OLLAMA_BASE_URL.rstrip("/") + "/api/chat"
    payload = json.dumps(
        {"model": settings.OLLAMA_MODEL, "messages": messages, "stream": False}
    ).encode()
    token = base64.b64encode(
        f"{settings.OLLAMA_USERNAME}:{settings.OLLAMA_PASSWORD}".encode()
    ).decode()
    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "ngrok-skip-browser-warning": "true",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        status = 401 if exc.code == 401 else 502
        message = (
            "The language model refused the tunnel login."
            if exc.code == 401
            else "The language model could not answer."
        )
        raise CopilotError(message, status=status) from None
    except (urllib.error.URLError, TimeoutError):
        raise CopilotError("The language model could not be reached.", status=502) from None
    return _message_text(raw)


def _message_text(raw):
    try:
        body = json.loads(raw.decode())
        text = body["message"]["content"]
    except (KeyError, TypeError, ValueError, UnicodeError):
        raise CopilotError("The language model could not answer.") from None
    if not isinstance(text, str) or not text.strip():
        raise CopilotError("The language model could not answer.")
    return text.strip()
