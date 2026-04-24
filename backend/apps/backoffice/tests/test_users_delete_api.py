from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.users.models import User
from apps.users.rbac import set_user_system_role


class BackofficeUsersDeleteAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin-users-delete@test.local",
            password="demo12345",
            first_name="Admin",
        )
        set_user_system_role(user=self.admin, role_code="administrator")
        self.admin_token = Token.objects.create(user=self.admin)
        self.admin_auth = {"HTTP_AUTHORIZATION": f"Token {self.admin_token.key}"}

        self.manager = User.objects.create_user(
            email="manager-users-delete@test.local",
            password="demo12345",
            first_name="Manager",
        )
        set_user_system_role(user=self.manager, role_code="manager")
        self.manager_token = Token.objects.create(user=self.manager)
        self.manager_auth = {"HTTP_AUTHORIZATION": f"Token {self.manager_token.key}"}

    def test_administrator_can_delete_user(self):
        target = User.objects.create_user(
            email="target-users-delete@test.local",
            password="demo12345",
            first_name="Target",
        )

        response = self.client.delete(
            reverse("backoffice_api:users-detail-update", kwargs={"id": target.id}),
            **self.admin_auth,
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(id=target.id).exists())

    def test_manager_cannot_delete_user(self):
        target = User.objects.create_user(
            email="target-users-delete-manager@test.local",
            password="demo12345",
            first_name="TargetManager",
        )

        response = self.client.delete(
            reverse("backoffice_api:users-detail-update", kwargs={"id": target.id}),
            **self.manager_auth,
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(User.objects.filter(id=target.id).exists())

    def test_administrator_cannot_delete_self(self):
        response = self.client.delete(
            reverse("backoffice_api:users-detail-update", kwargs={"id": self.admin.id}),
            **self.admin_auth,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(User.objects.filter(id=self.admin.id).exists())
