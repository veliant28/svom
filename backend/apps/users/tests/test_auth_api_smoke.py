from django.urls import reverse
from django.core import mail
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.users.models import User


class AuthAPISmokeTests(APITestCase):
    def setUp(self):
        self.password = "demo12345"
        self.user = User.objects.create_user(
            email="auth-demo@test.local",
            password=self.password,
            first_name="Auth",
            last_name="Demo",
        )

    def test_login_current_user_logout_flow(self):
        login_response = self.client.post(
            reverse("users_api:auth-login"),
            {
                "email": self.user.email,
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn("token", login_response.data)
        self.assertEqual(login_response.data["user"]["email"], self.user.email)

        token = login_response.data["token"]
        auth_headers = {"HTTP_AUTHORIZATION": f"Token {token}"}

        current_user_response = self.client.get(reverse("users_api:auth-current-user"), **auth_headers)
        self.assertEqual(current_user_response.status_code, status.HTTP_200_OK)
        self.assertEqual(current_user_response.data["email"], self.user.email)

        logout_response = self.client.post(reverse("users_api:auth-logout"), {}, format="json", **auth_headers)
        self.assertEqual(logout_response.status_code, status.HTTP_204_NO_CONTENT)

        after_logout_response = self.client.get(reverse("users_api:auth-current-user"), **auth_headers)
        self.assertEqual(after_logout_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_is_not_blocked_by_csrf_when_session_cookie_exists(self):
        session_client = APIClient(enforce_csrf_checks=True)
        session_client.force_login(self.user)

        login_response = session_client.post(
            reverse("users_api:auth-login"),
            {
                "email": self.user.email,
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn("token", login_response.data)

    def test_profile_update_accepts_spaced_phone_format(self):
        login_response = self.client.post(
            reverse("users_api:auth-login"),
            {
                "email": self.user.email,
                "password": self.password,
            },
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        token = login_response.data["token"]
        auth_headers = {"HTTP_AUTHORIZATION": f"Token {token}"}

        profile_update_response = self.client.patch(
            reverse("users_api:auth-profile-update"),
            {"phone": "38 (000) 111-22-33"},
            format="json",
            **auth_headers,
        )
        self.assertEqual(profile_update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(profile_update_response.data["phone"], "38(000)111-22-33")

        profile_update_plus_response = self.client.patch(
            reverse("users_api:auth-profile-update"),
            {"phone": "+38 (000) 111-22-33"},
            format="json",
            **auth_headers,
        )
        self.assertEqual(profile_update_plus_response.status_code, status.HTTP_200_OK)
        self.assertEqual(profile_update_plus_response.data["phone"], "38(000)111-22-33")

    def test_profile_update_persists_middle_name(self):
        login_response = self.client.post(
            reverse("users_api:auth-login"),
            {
                "email": self.user.email,
                "password": self.password,
            },
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        token = login_response.data["token"]
        auth_headers = {"HTTP_AUTHORIZATION": f"Token {token}"}

        profile_update_response = self.client.patch(
            reverse("users_api:auth-profile-update"),
            {"middle_name": "Геннадиевич"},
            format="json",
            **auth_headers,
        )
        self.assertEqual(profile_update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(profile_update_response.data["middle_name"], "Геннадиевич")

        current_user_response = self.client.get(reverse("users_api:auth-current-user"), **auth_headers)
        self.assertEqual(current_user_response.status_code, status.HTTP_200_OK)
        self.assertEqual(current_user_response.data["middle_name"], "Геннадиевич")

    def test_register_creates_user_profile_and_returns_token(self):
        response = self.client.post(
            reverse("users_api:auth-register"),
            {
                "email": "new-customer@test.local",
                "password": "StrongPass12345",
                "first_name": "Ivan",
                "last_name": "Petrenko",
                "middle_name": "Ivanovych",
                "phone": "38 (099) 111-22-33",
                "preferred_language": "ru",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("token", response.data)
        self.assertEqual(response.data["user"]["email"], "new-customer@test.local")
        self.assertEqual(response.data["user"]["first_name"], "Ivan")
        self.assertEqual(response.data["user"]["last_name"], "Petrenko")
        self.assertEqual(response.data["user"]["middle_name"], "Ivanovych")
        self.assertEqual(response.data["user"]["phone"], "38(099)111-22-33")
        self.assertEqual(response.data["user"]["preferred_language"], "ru")

    def test_password_reset_sends_email_and_confirm_changes_password(self):
        reset_response = self.client.post(
            reverse("users_api:auth-password-reset"),
            {
                "email": self.user.email,
                "locale": "ru",
            },
            format="json",
            HTTP_ORIGIN="https://svom.test",
        )

        self.assertEqual(reset_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("https://svom.test/ru/reset-password/", mail.outbox[0].body)

        reset_path = mail.outbox[0].body.split("https://svom.test/ru/reset-password/", 1)[1].splitlines()[0]
        uid, token = reset_path.split("/", 1)

        confirm_response = self.client.post(
            reverse("users_api:auth-password-reset-confirm"),
            {
                "uid": uid,
                "token": token,
                "new_password": "NewStrongPass12345",
            },
            format="json",
        )

        self.assertEqual(confirm_response.status_code, status.HTTP_204_NO_CONTENT)
        login_response = self.client.post(
            reverse("users_api:auth-login"),
            {
                "email": self.user.email,
                "password": "NewStrongPass12345",
            },
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
