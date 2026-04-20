from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.users.models import User


class AuthAPISmokeTests(APITestCase):
    def setUp(self):
        self.password = "demo12345"
        self.user = User.objects.create_user(
            email="auth-demo@test.local",
            username="auth-demo",
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
