from __future__ import annotations

from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.commerce.models import NovaPoshtaSenderProfile
from apps.users.models import User


class BackofficeNovaPoshtaSenderProfileAPITests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="np-sender-staff@test.local",
            username="np-sender-staff",
            password="demo12345",
            is_staff=True,
        )
        self.staff_token = Token.objects.create(user=self.staff)

    def _auth(self) -> dict[str, str]:
        return {"HTTP_AUTHORIZATION": f"Token {self.staff_token.key}"}

    def _payload(self, *, api_token: str) -> dict[str, object]:
        return {
            "name": "Main sender",
            "sender_type": "private_person",
            "api_token": api_token,
            "counterparty_ref": "counterparty-ref-1",
            "contact_ref": "contact-ref-1",
            "address_ref": "address-ref-1",
            "city_ref": "city-ref-1",
            "phone": "+380671111111",
            "contact_name": "Іван Іванов",
            "is_active": True,
            "is_default": True,
        }

    def test_sender_token_is_stored_and_can_be_overwritten(self):
        create_response = self.client.post(
            reverse("backoffice_api:nova-poshta-sender-list-create"),
            self._payload(api_token="token-create-1111"),
            format="json",
            **self._auth(),
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        sender_id = create_response.data["id"]

        sender = NovaPoshtaSenderProfile.objects.get(id=sender_id)
        self.assertEqual(sender.api_token, "token-create-1111")

        update_response = self.client.patch(
            reverse("backoffice_api:nova-poshta-sender-update", kwargs={"id": sender_id}),
            {"api_token": "token-update-2222"},
            format="json",
            **self._auth(),
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)

        sender.refresh_from_db()
        self.assertEqual(sender.api_token, "token-update-2222")

        keep_response = self.client.patch(
            reverse("backoffice_api:nova-poshta-sender-update", kwargs={"id": sender_id}),
            {"phone": "+380672222222"},
            format="json",
            **self._auth(),
        )
        self.assertEqual(keep_response.status_code, status.HTTP_200_OK)

        sender.refresh_from_db()
        self.assertEqual(sender.api_token, "token-update-2222")

