"""API views. Figures are copied from the loss engine payload."""

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from accounts.views import read_json

from .copilot import CopilotError, clean_history, reply
from .engine import get_payload


def portfolio(_request):
    return JsonResponse(get_payload())


def buildings(_request):
    return JsonResponse({"buildings": get_payload()["buildings"]})


def building_detail(_request, loc_id):
    building = next((item for item in get_payload()["buildings"] if item["loc_id"] == loc_id), None)
    if building is None:
        return JsonResponse({"detail": "Building not found."}, status=404)
    return JsonResponse(building)


def loss_curve(request):
    payload = get_payload()
    assumption = request.GET.get("assumption", "reference")
    if not any(item["id"] == assumption for item in payload["scenarios"]):
        return JsonResponse({"detail": "Unknown damage assumption."}, status=404)
    points = [point for point in payload["ep_points"] if point["scenario_id"] == assumption]
    return JsonResponse({"assumption": assumption, "points": points})


def hotspots(_request):
    return JsonResponse({"hotspots": get_payload()["hotspots"]})


@require_POST
def copilot(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)
    data = read_json(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON."}, status=400)
    message = data.get("message", "")
    if not isinstance(message, str) or not message.strip():
        return JsonResponse({"error": "Enter a message."}, status=400)
    tier = data.get("tier", "")
    assumption = data.get("assumption", "")
    selected_id = data.get("selected_id", "")
    if not isinstance(tier, str) or not isinstance(assumption, str) or not isinstance(selected_id, str):
        return JsonResponse({"error": "Invalid JSON."}, status=400)
    try:
        text, actions = reply(
            message.strip()[:2000],
            clean_history(data.get("history")),
            tier.strip(),
            assumption.strip(),
            selected_id.strip(),
        )
    except CopilotError as exc:
        return JsonResponse({"error": exc.message}, status=exc.status)
    return JsonResponse({"reply": text, "actions": actions})
