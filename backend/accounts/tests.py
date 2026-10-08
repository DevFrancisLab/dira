import json

from django.test import Client, TestCase

from accounts.models import User

PASSWORD = "Valid-password-9"
EMAIL = "user@example.com"
NAME = "Francis Masila"


def post_json(client, path, payload, **extra):
    return client.post(path, data=json.dumps(payload), content_type="application/json", **extra)


class RegistrationTests(TestCase):
    def test_successful_registration(self):
        response = post_json(
            self.client,
            "/api/auth/register/",
            {"name": NAME, "email": "User@Example.com", "password": PASSWORD},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"id": response.json()["id"], "name": NAME, "email": EMAIL})
        user = User.objects.get(email=EMAIL)
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotIn("password", response.json())

    def test_duplicate_email_registration(self):
        payload = {"name": NAME, "email": EMAIL, "password": PASSWORD}
        first = post_json(self.client, "/api/auth/register/", payload)
        second = post_json(
            self.client,
            "/api/auth/register/",
            {"name": "Someone Else", "email": "USER@example.com", "password": PASSWORD},
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(second.json(), {"error": "An account with this email already exists."})
        self.assertEqual(User.objects.filter(email=EMAIL).count(), 1)


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
        self.assertEqual(set(body), {"id", "name", "email"})

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
