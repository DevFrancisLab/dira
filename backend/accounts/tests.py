import json

from django.test import Client, TestCase

from accounts.audit import LOGIN_FAILED, LOGIN_SUCCEEDED, USER_CREATED, USER_DEACTIVATED, USER_REACTIVATED
from accounts.models import AuditEvent, User

PASSWORD = "Valid-password-9"
EMAIL = "user@example.com"
NAME = "Francis Masila"


def post_json(client, path, payload, **extra):
    return client.post(path, data=json.dumps(payload), content_type="application/json", **extra)


class RegistrationTests(TestCase):
    def test_public_registration_is_disabled(self):
        response = post_json(
            self.client,
            "/api/auth/register/",
            {"name": NAME, "email": EMAIL, "password": PASSWORD},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"error": "Public registration is disabled."})
        self.assertFalse(User.objects.filter(email=EMAIL).exists())


class SessionTests(TestCase):
    def setUp(self):
        User.objects.create_user(email=EMAIL, name=NAME, password=PASSWORD)

    def test_successful_login(self):
        response = post_json(
            self.client,
            "/api/auth/login/",
            {"email": "User@Example.com", "password": PASSWORD},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], EMAIL)
        self.assertEqual(response.json()["name"], NAME)
        self.assertNotIn("password", response.json())
        self.assertIn("_auth_user_id", self.client.session)

    def test_invalid_login(self):
        response = post_json(
            self.client,
            "/api/auth/login/",
            {"email": EMAIL, "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"error": "Invalid email or password."})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_me_while_authenticated(self):
        post_json(self.client, "/api/auth/login/", {"email": EMAIL, "password": PASSWORD})

        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["email"], EMAIL)
        self.assertEqual(body["name"], NAME)
        self.assertEqual(set(body), {"id", "name", "email", "is_staff"})
        self.assertFalse(body["is_staff"])

    def test_me_while_unauthenticated(self):
        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"error": "Authentication required."})

    def test_successful_logout(self):
        post_json(self.client, "/api/auth/login/", {"email": EMAIL, "password": PASSWORD})

        response = post_json(self.client, "/api/auth/logout/", {})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"detail": "Logged out."})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_me_after_logout(self):
        post_json(self.client, "/api/auth/login/", {"email": EMAIL, "password": PASSWORD})
        post_json(self.client, "/api/auth/logout/", {})

        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"error": "Authentication required."})


class CsrfTests(TestCase):
    def test_login_requires_csrf_token_and_accepts_the_issued_token(self):
        User.objects.create_user(email=EMAIL, name=NAME, password=PASSWORD)
        client = Client(enforce_csrf_checks=True)

        blocked = post_json(client, "/api/auth/login/", {"email": EMAIL, "password": PASSWORD})
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(blocked.json(), {"error": "CSRF verification failed."})

        issued = client.get("/api/auth/csrf/")
        self.assertEqual(issued.status_code, 200)
        token = issued.json()["csrfToken"]

        allowed = post_json(
            client,
            "/api/auth/login/",
            {"email": EMAIL, "password": PASSWORD},
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json()["email"], EMAIL)


def patch_json(client, path, payload):
    return client.patch(path, data=json.dumps(payload), content_type="application/json")


class AdminApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com",
            name="Dira Admin",
            password=PASSWORD,
            is_staff=True,
        )
        self.member = User.objects.create_user(email=EMAIL, name=NAME, password=PASSWORD)

    def test_admin_endpoints_require_authentication(self):
        response = self.client.get("/api/admin/users/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"error": "Authentication required."})

    def test_normal_user_is_forbidden(self):
        post_json(self.client, "/api/auth/login/", {"email": EMAIL, "password": PASSWORD})
        response = self.client.get("/api/admin/stats/")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"error": "Administrator access required."})

    def test_staff_can_list_and_read_real_stats(self):
        post_json(self.client, "/api/auth/login/", {"email": "admin@example.com", "password": PASSWORD})

        stats = self.client.get("/api/admin/stats/")
        listing = self.client.get("/api/admin/users/")

        self.assertEqual(stats.status_code, 200)
        self.assertEqual(
            stats.json(),
            {"total_users": 2, "active_users": 2, "inactive_users": 0, "administrators": 1},
        )
        self.assertEqual(listing.status_code, 200)
        emails = {row["email"] for row in listing.json()["users"]}
        self.assertEqual(emails, {"admin@example.com", EMAIL})
        self.assertNotIn("password", listing.json()["users"][0])

    def test_admin_creates_user_and_rejects_duplicate_email(self):
        post_json(self.client, "/api/auth/login/", {"email": "admin@example.com", "password": PASSWORD})
        payload = {
            "first_name": "Amina",
            "last_name": "Otieno",
            "email": "Amina@Example.com",
            "phone": "+254 712 345678",
            "role": "user",
        }
        created = post_json(self.client, "/api/admin/users/", payload)
        duplicate = post_json(self.client, "/api/admin/users/", payload)

        self.assertEqual(created.status_code, 201)
        body = created.json()
        self.assertEqual(body["user"]["email"], "amina@example.com")
        self.assertEqual(body["user"]["role"], "user")
        self.assertNotIn("password", body["user"])
        temporary = body["temporary_password"]
        user = User.objects.get(email="amina@example.com")
        self.assertNotEqual(user.password, temporary)
        self.assertTrue(user.check_password(temporary))
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate.json(), {"error": "An account with this email already exists."})
        self.assertTrue(AuditEvent.objects.filter(action=USER_CREATED, subject_email="amina@example.com").exists())

    def test_admin_can_deactivate_and_reactivate_user(self):
        post_json(self.client, "/api/auth/login/", {"email": "admin@example.com", "password": PASSWORD})

        disabled = patch_json(self.client, f"/api/admin/users/{self.member.pk}/", {"is_active": False})
        self.assertEqual(disabled.status_code, 200)
        self.assertFalse(disabled.json()["is_active"])

        self.client.logout()
        blocked = post_json(self.client, "/api/auth/login/", {"email": EMAIL, "password": PASSWORD})
        self.assertEqual(blocked.status_code, 401)
        self.assertNotIn("_auth_user_id", self.client.session)

        post_json(self.client, "/api/auth/login/", {"email": "admin@example.com", "password": PASSWORD})
        restored = patch_json(self.client, f"/api/admin/users/{self.member.pk}/", {"is_active": True})
        self.assertEqual(restored.status_code, 200)
        self.assertTrue(restored.json()["is_active"])
        self.assertTrue(AuditEvent.objects.filter(action=USER_DEACTIVATED, subject_email=EMAIL).exists())
        self.assertTrue(AuditEvent.objects.filter(action=USER_REACTIVATED, subject_email=EMAIL).exists())

        stats = self.client.get("/api/admin/stats/")
        self.assertEqual(stats.json()["active_users"], 2)
        self.assertEqual(stats.json()["inactive_users"], 0)

    def test_login_events_are_recorded(self):
        post_json(self.client, "/api/auth/login/", {"email": EMAIL, "password": "wrong-password"})
        post_json(self.client, "/api/auth/login/", {"email": EMAIL, "password": PASSWORD})

        self.assertTrue(AuditEvent.objects.filter(action=LOGIN_FAILED, subject_email=EMAIL).exists())
        self.assertTrue(AuditEvent.objects.filter(action=LOGIN_SUCCEEDED, subject_email=EMAIL).exists())
        stored = AuditEvent.objects.filter(subject_email=EMAIL)
        self.assertFalse(any(PASSWORD in event.subject_email or "password" in event.action for event in stored))
