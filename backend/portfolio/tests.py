import json
from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from accounts.models import User
from accounts.tests import PASSWORD, password_only, post_json
from portfolio.copilot import CopilotError

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

    def test_a_dropped_tunnel_is_reported_as_unreachable(self):
        with patch("portfolio.copilot.urllib.request.urlopen", side_effect=ConnectionResetError):
            response = post_json(self.client, "/api/copilot/", {"message": "Hello"})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["error"], "The language model could not be reached.")

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


class IngestTests(TestCase):
    def setUp(self):
        password_only()
        User.objects.create_user(email="ingest@example.com", name="Ingest User", password=PASSWORD)
        post_json(self.client, "/api/auth/login/", {"email": "ingest@example.com", "password": PASSWORD})
        patched = patch("portfolio.ingest.ask_ollama", side_effect=CopilotError("down"))
        patched.start()
        self.addCleanup(patched.stop)

    def test_anonymous_upload_is_rejected(self):
        self.client.logout()
        response = self.client.post("/api/copilot/ingest/", {"file": _csv()})
        self.assertEqual(response.status_code, 401)

    def test_missing_file_is_rejected(self):
        response = self.client.post("/api/copilot/ingest/")
        self.assertEqual(response.status_code, 400)

    def test_csv_locations_are_returned(self):
        response = self.client.post("/api/copilot/ingest/", {"file": _csv()})
        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["status"], "ingested")
        self.assertEqual(body["page"], "map")
        self.assertEqual([row["loc_id"] for row in body["rows"]], ["UP-1", "UP-2"])
        self.assertIn("2 locations", body["summary"])

    def test_an_unreadable_image_returns_sample_locations(self):
        upload = SimpleUploadedFile("photo.png", b"\x89PNG\r\n", content_type="image/png")
        response = self.client.post("/api/copilot/ingest/", {"file": upload})
        body = response.json()
        self.assertEqual(body["status"], "sample")
        self.assertEqual(body["rows"][0]["loc_id"], "SAMPLE-01")
        self.assertIn("sample", body["summary"].lower())


PROMPT = (
    "Show me the highest-risk buildings in Nairobi under the extreme scenario, "
    "zoom into them, explain why they are high risk, and generate a PDF report"
)


class RiskBriefTests(TestCase):
    def setUp(self):
        password_only()
        User.objects.create_user(email="brief@example.com", name="Brief User", password=PASSWORD)
        post_json(self.client, "/api/auth/login/", {"email": "brief@example.com", "password": PASSWORD})

    def test_the_extreme_prompt_frames_buildings_and_waits_for_approval(self):
        with patch("portfolio.copilot.urllib.request.urlopen") as urlopen:
            response = post_json(self.client, "/api/copilot/", {"message": PROMPT})
        urlopen.assert_not_called()
        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertIn("susceptibility proxy", body["reply"])
        self.assertIn("Approve", body["reply"])
        self.assertEqual(body["actions"][0], {"name": "set_scenario", "scenario": "reference"})
        self.assertEqual(body["actions"][1], {"name": "set_tier", "tier": "extreme"})
        ids = body["actions"][2]["ids"]
        self.assertGreater(len(ids), 0)
        self.assertLessEqual(len(ids), 8)
        self.assertIn(ids[0], body["reply"])
        self.assertTrue(body["review"]["required"])
        self.assertEqual(body["review"]["tier"], "extreme")

    def test_pdf_is_created_only_after_approval(self):
        refused = post_json(
            self.client,
            "/api/copilot/report/",
            {"approved": False, "tier": "extreme", "assumption": "reference"},
        )
        self.assertEqual(refused.status_code, 400)
        self.assertNotIn(b"%PDF", refused.content)

        approved = post_json(
            self.client,
            "/api/copilot/report/",
            {"approved": True, "tier": "extreme", "assumption": "reference"},
        )
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved["Content-Type"], "application/pdf")
        self.assertTrue(approved.content.startswith(b"%PDF"))
        self.assertIn(b"brief@example.com", approved.content)
        self.assertIn(b"Approved by", approved.content)

    def test_anonymous_report_is_rejected(self):
        self.client.logout()
        response = post_json(
            self.client,
            "/api/copilot/report/",
            {"approved": True, "tier": "extreme", "assumption": "reference"},
        )
        self.assertEqual(response.status_code, 401)


def _csv():
    text = (
        "loc_id,lat,lon,housing_class,tiv_kes\n"
        "UP-1,-1.29,36.82,permanent_masonry,1000000\n"
        "UP-2,-1.30,36.81,informal_iron_sheet,500000\n"
    )
    return SimpleUploadedFile("sites.csv", text.encode(), content_type="text/csv")
