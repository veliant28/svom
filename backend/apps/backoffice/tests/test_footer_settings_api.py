from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.marketing.models import FooterSettings
from apps.users.models import User
from apps.users.rbac import set_user_system_role


class BackofficeFooterSettingsAPITests(APITestCase):
    def setUp(self):
        self.administrator = User.objects.create_user(
            email="admin-footer@test.local",
            first_name="Admin",
            password="pass12345",
            is_staff=True,
        )
        self.manager = User.objects.create_user(
            email="manager-footer@test.local",
            first_name="Manager",
            password="pass12345",
            is_staff=True,
        )

        set_user_system_role(user=self.administrator, role_code="administrator")
        set_user_system_role(user=self.manager, role_code="manager")

        self.admin_token = Token.objects.create(user=self.administrator)
        self.manager_token = Token.objects.create(user=self.manager)

    def test_administrator_can_read_and_update_footer_settings(self):
        get_response = self.client.get(
            reverse("backoffice_api:settings-footer"),
            HTTP_AUTHORIZATION=f"Token {self.admin_token.key}",
        )
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        self.assertIn("working_hours", get_response.data)
        self.assertIn("phone", get_response.data)

        patch_response = self.client.patch(
            reverse("backoffice_api:settings-footer"),
            {
                "working_hours": "ПН-ПТ 09:00-18:00",
                "phone": "+38(067)111-22-33",
            },
            format="json",
            HTTP_AUTHORIZATION=f"Token {self.admin_token.key}",
        )
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)

        settings = FooterSettings.objects.get(code=FooterSettings.DEFAULT_CODE)
        self.assertEqual(settings.working_hours, "ПН-ПТ 09:00-18:00")
        self.assertEqual(settings.phone, "+38(067)111-22-33")

    def test_manager_without_capability_cannot_access_footer_settings(self):
        response = self.client.get(
            reverse("backoffice_api:settings-footer"),
            HTTP_AUTHORIZATION=f"Token {self.manager_token.key}",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
