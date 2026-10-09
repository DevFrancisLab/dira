import json
from io import BytesIO
from unittest.mock import patch

from django.test import TestCase, override_settings

from accounts.models import User
from accounts.tests import PASSWORD, password_only, post_json

URL = "https://ollama.example.test"
MODEL = "llama3.2:3b"


@override_settings(
    OLLAMA_BASE_URL=URL,
    OLLAMA_USERNAME="dira",
    OLLAMA_PASSWORD="tunnel-password",
    OLLAMA_MODEL=MODEL,
)
class CopilotTests(TestCase):
    def setUp(self):
        password_only()
        User.objects.create_user(email="copilot@example.com", name="Copilot User", password=PASSWORD)
        post_json(self.client, "/api/auth/login/", {"email": "copilot@example.com", "password": PASSWORD})

    def test_anonymous_request_is_rejected(self):
        self.client.logout()
        response = post_json(self.client, "/api/copilot/", {"message": "Hello"})
        self.assertEqual(response.status_code, 401)

    def test_reply_comes_from_ollama(self):
        captured = {}

        class Response(BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        def capture(request, timeout):
            captured["url"] = request.full_url
            captured["auth"] = request.get_header("Authorization")
            captured["body"] = json.loads(request.data.decode())
            captured["timeout"] = timeout
            return Response(json.dumps({"message": {"role": "assistant", "content": "The proxy is not a depth."}}).encode())

        with patch("portfolio.copilot.urllib.request.urlopen", side_effect=capture):
            response = post_json(
                self.client,
                "/api/copilot/",
                {
                    "message": "What does the proxy mean?",
                    "history": [{"role": "user", "content": "Earlier"}, {"role": "assistant", "content": "Noted"}],
                    "tier": "common",
                    "assumption": "reference",
                    "selected_id": "",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reply"], "The proxy is not a depth.")
        self.assertEqual(response.json()["actions"], [])
        self.assertEqual(captured["url"], URL + "/api/chat")
        self.assertTrue(captured["auth"].startswith("Basic "))
        self.assertEqual(captured["body"]["model"], MODEL)
        self.assertEqual(captured["body"]["stream"], False)
        self.assertEqual(captured["body"]["messages"][-1], {"role": "user", "content": "What does the proxy mean?"})
        self.assertIn("susceptibility proxy", captured["body"]["messages"][0]["content"])
        self.assertNotIn("tunnel-password", json.dumps(response.json()))

    @override_settings(OLLAMA_PASSWORD="")
    def test_missing_tunnel_password_does_not_call_ollama(self):
        with patch("portfolio.copilot.urllib.request.urlopen") as urlopen:
            response = post_json(self.client, "/api/copilot/", {"message": "Hello"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"], "The language model is not configured.")
        urlopen.assert_not_called()

    def test_plain_requests_open_sections_and_zoom_the_map(self):
        def respond(_request, timeout=120):
            class Response(BytesIO):
                def __enter__(self):
                    return self

                def __exit__(self, *_args):
                    return False

            return Response(json.dumps({"message": {"role": "assistant", "content": "Done."}}).encode())

        with patch("portfolio.copilot.urllib.request.urlopen", side_effect=respond):
            reports = post_json(self.client, "/api/copilot/", {"message": "Go to the reports section"})
            zoom = post_json(self.client, "/api/copilot/", {"message": "zoom in to the map"})
        self.assertEqual(reports.json()["actions"], [{"name": "navigate", "page": "reports"}])
        self.assertEqual(
            zoom.json()["actions"],
            [{"name": "navigate", "page": "map"}, {"name": "zoom_in"}],
        )

    def test_model_actions_are_kept_and_unknown_actions_are_dropped(self):
        content = json.dumps(
            {
                "reply": "Opening exposure.",
                "actions": [
                    {"name": "navigate", "page": "exposure"},
                    {"name": "delete_portfolio"},
                ],
            }
        )

        class Response(BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        with patch(
            "portfolio.copilot.urllib.request.urlopen",
            return_value=Response(json.dumps({"message": {"content": content}}).encode()),
        ):
            response = post_json(self.client, "/api/copilot/", {"message": "Please open exposure"})
        self.assertEqual(response.json()["reply"], "Opened Exposure.")
        self.assertEqual(response.json()["actions"], [{"name": "navigate", "page": "exposure"}])
