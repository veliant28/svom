from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.core.models import EmailDeliverySettings
from apps.users.models import User


class BackofficeEmailSettingsAPITests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="email-settings-admin@test.local",
            first_name="Admin",
            password="pass12345",
            is_staff=True,
            is_superuser=True,
        )
        self.token = Token.objects.create(user=self.staff)
        self.auth = {"HTTP_AUTHORIZATION": f"Token {self.token.key}"}

    def test_resend_provider_applies_preset_and_masks_api_key(self):
        response = self.client.patch(
            reverse("backoffice_api:settings-email"),
            {
                "provider": EmailDeliverySettings.PROVIDER_RESEND_SMTP,
                "is_enabled": True,
                "from_name": "SVOM",
                "from_email": "no-reply@svom.com.ua",
                "host_password": "re_secret_key_123456789",
            },
            format="json",
            **self.auth,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["provider"], EmailDeliverySettings.PROVIDER_RESEND_SMTP)
        self.assertEqual(response.data["host"], "smtp.resend.com")
        self.assertEqual(response.data["port"], 587)
        self.assertEqual(response.data["host_user"], "resend")
        self.assertTrue(response.data["use_tls"])
        self.assertFalse(response.data["use_ssl"])
        self.assertEqual(response.data["timeout"], 10)
        self.assertEqual(response.data["frontend_base_url"], "https://svom.com.ua")
        self.assertNotIn("host_password", response.data)
        self.assertIn("host_password_masked", response.data)
        self.assertNotEqual(response.data["host_password_masked"], "re_secret_key_123456789")

    def test_test_email_returns_safe_message_without_saved_secret(self):
        settings = EmailDeliverySettings.objects.create(
            provider=EmailDeliverySettings.PROVIDER_RESEND_SMTP,
            is_enabled=True,
            from_name="SVOM",
            from_email="no-reply@svom.com.ua",
            host="smtp.resend.com",
            port=587,
            host_user="resend",
            host_password="re_secret_key_123456789",
            use_tls=True,
            use_ssl=False,
            frontend_base_url="https://svom.com.ua",
        )

        with patch("apps.core.services.email_delivery.EmailMessage.send", side_effect=RuntimeError(settings.host_password)):
            response = self.client.post(
                reverse("backoffice_api:settings-email-test"),
                {"recipient": "ops@test.local"},
                format="json",
                **self.auth,
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["ok"])
        self.assertNotIn(settings.host_password, response.data["message"])
        settings.refresh_from_db()
        self.assertNotIn(settings.host_password, settings.last_connection_message)
