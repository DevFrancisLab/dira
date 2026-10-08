"""Deliver a one-time code by email or SMS. Secrets stay in the environment."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.mail import send_mail


class DeliveryError(Exception):
    """The code was not delivered. The message must not contain the code or a secret."""


def deliver(method, user, code):
    if method == "email":
        deliver_email(user, code)
        return
    if method == "sms":
        deliver_sms(user, code)
        return
    raise DeliveryError("That verification method is not available.")


def deliver_email(user, code):
    send_mail(
        subject="Your Dira verification code",
        message=(
            "Dira\n\n"
            f"Your verification code is {code}.\n\n"
            "This code expires in 5 minutes.\n\n"
            "If you did not try to sign in, you can ignore this message. "
            "Do not share this code with anyone."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def deliver_sms(user, code):
    destination = sms_destination(user.phone)
    if not destination:
        raise DeliveryError("This account has no phone number.")
    message = (
        f"Dira verification code: {code}. "
        "It expires in 5 minutes. Do not share this code."
    )
    send_sms(destination, message)


def sms_destination(phone):
    raw = (phone or "").strip()
    digits = "".join(character for character in raw if character.isdigit())
    if not digits:
        return ""
    if raw.startswith("+"):
        return "+" + digits
    return digits


def sms_endpoint(username):
    if username == "sandbox":
        return "https://api.sandbox.africastalking.com/version1/messaging"
    return "https://api.africastalking.com/version1/messaging"


def send_sms(phone, message):
    if settings.EMAIL_BACKEND.endswith("locmem.EmailBackend"):
        raise DeliveryError("Live SMS is disabled during tests.")
    username = os.environ.get("AT_USERNAME", "").strip()
    api_key = os.environ.get("AT_API_KEY", "").strip()
    sender = os.environ.get("AT_SENDER_ID", "").strip()
    if not username or not api_key:
        raise DeliveryError("SMS delivery is not configured.")

    payload = {"username": username, "to": phone, "message": message}
    if sender:
        payload["from"] = sender
    request = urllib.request.Request(
        sms_endpoint(username),
        data=urllib.parse.urlencode(payload).encode(),
        method="POST",
        headers={
            "apiKey": api_key,
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read()
    except (urllib.error.URLError, TimeoutError):
        raise DeliveryError("SMS could not be sent.") from None

    if not _sms_accepted(raw):
        raise DeliveryError("SMS could not be sent.")


def _sms_accepted(raw):
    try:
        body = json.loads(raw.decode())
        recipients = body["SMSMessageData"]["Recipients"]
    except (KeyError, TypeError, ValueError, UnicodeError):
        return False
    if not recipients:
        return False
    return all(item.get("statusCode") in {100, 101, 102} for item in recipients)
