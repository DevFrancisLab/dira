"""API views. Figures are copied from the loss engine payload."""

from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST

from accounts.views import read_json

from .copilot import CopilotError, clean_history, reply
from .engine import get_payload
from .ingest import ingest_upload
from .risk_brief import build_brief, is_risk_brief, render_pdf


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
    if is_risk_brief(message):
        return JsonResponse(build_brief())
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


@require_POST
def ingest(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)
    upload = request.FILES.get("file")
    if upload is None:
        return JsonResponse({"error": "Choose a file."}, status=400)
    return JsonResponse(ingest_upload(upload))


@require_POST
def risk_report(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)
    data = read_json(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON."}, status=400)
    if data.get("approved") is not True:
        return JsonResponse({"error": "The report stays unapproved until you approve it."}, status=400)
    if data.get("tier") != "extreme" or data.get("assumption") != "reference":
        return JsonResponse({"error": "That report is not available."}, status=400)
    document = render_pdf(request.user.email)
    response = HttpResponse(document, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="dira-extreme-risk-report.pdf"'
    return response
