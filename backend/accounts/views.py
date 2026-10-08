"""Session authentication API. Loss calculations stay in loss_engine."""

import json

from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .audit import LOGIN_FAILED, LOGIN_SUCCEEDED, record
from .models import User


def csrf_failure(request, reason=""):
    return JsonResponse({"error": "CSRF verification failed."}, status=403)


def user_payload(user):
    return {"id": user.pk, "name": user.name, "email": user.email, "is_staff": user.is_staff}


def read_json(request):
    if not request.body:
        return {}
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def text_field(data, key):
    value = data.get(key, "")
    if not isinstance(value, str):
        return ""
    return value.strip()


@require_GET
@ensure_csrf_cookie
def csrf(request):
    return JsonResponse({"csrfToken": get_token(request)})


@require_POST
def register(_request):
    return JsonResponse({"error": "Public registration is disabled."}, status=403)


@require_POST
def login_view(request):
    data = read_json(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    email = text_field(data, "email").lower()
    password = data.get("password", "")
    if not email or not isinstance(password, str) or not password:
        return JsonResponse({"error": "Invalid email or password."}, status=401)

    user = authenticate(request, email=email, password=password)
    if user is None:
        record(LOGIN_FAILED, subject_email=email, actor=User.objects.filter(email=email).first())
        return JsonResponse({"error": "Invalid email or password."}, status=401)

    login(request, user)
    record(LOGIN_SUCCEEDED, subject_email=user.email, actor=user)
    return JsonResponse(user_payload(user))


@require_POST
def logout_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)
    logout(request)
    return JsonResponse({"detail": "Logged out."})


@require_GET
def me(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)
    return JsonResponse(user_payload(request.user))
