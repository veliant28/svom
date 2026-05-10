from __future__ import annotations

from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.security.models import SecurityActor, SecurityBlock, SecurityEvent
from apps.security.services.enforcement import (
    SECURITY_BLOCK_MODE_HARD,
    SECURITY_BLOCK_MODE_SOFT,
    touch_block_enforcement_revision,
)
from apps.users.models import User


class SecurityBlockEnforcementTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email="blocked-user@test.local",
            password="StrongPass12345",
            first_name="Blocked",
            last_name="User",
        )
        self.token = Token.objects.create(user=self.user)

    def _auth(self) -> dict[str, str]:
        return {"HTTP_AUTHORIZATION": f"Token {self.token.key}"}

    def _create_ip_block(self, ip: str, *, mode: str = SECURITY_BLOCK_MODE_HARD, status_value: str = SecurityActor.STATUS_BLOCKED) -> SecurityBlock:
        actor = SecurityActor.objects.create(
            source_identifier=ip,
            source_ip=ip,
            source_kind=SecurityActor.SOURCE_IPV4,
            status=status_value,
        )
        return SecurityBlock.objects.create(
            actor=actor,
            block_type=SecurityBlock.TYPE_IP,
            value=ip,
            status=SecurityBlock.STATUS_ACTIVE,
            blocked_at=timezone.now(),
            reason="Test block",
            metadata={"block_mode": mode},
        )

    def test_blocked_ip_cannot_access_protected_storefront_api(self):
        self._create_ip_block("203.0.113.50")

        response = self.client.get(
            reverse("commerce_api:cart-retrieve"),
            HTTP_X_FORWARDED_FOR="203.0.113.50",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()["code"], "security_blocked")

    def test_blocked_ip_cannot_access_catalog_products_in_hard_mode(self):
        self._create_ip_block("203.0.113.51", mode=SECURITY_BLOCK_MODE_HARD)

        response = self.client.get(
            reverse("catalog_api:product-list"),
            HTTP_X_FORWARDED_FOR="203.0.113.51",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()["code"], "security_blocked")

    def test_whitelisted_ip_bypasses_active_block(self):
        self._create_ip_block("203.0.113.52", mode=SECURITY_BLOCK_MODE_HARD, status_value=SecurityActor.STATUS_WHITELISTED)

        response = self.client.get(
            reverse("catalog_api:product-list"),
            HTTP_X_FORWARDED_FOR="203.0.113.52",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_blocked_authenticated_user_cannot_access_with_existing_token(self):
        actor = SecurityActor.objects.create(
            source_identifier=str(self.user.id),
            source_kind=SecurityActor.SOURCE_UNKNOWN,
            user=self.user,
            status=SecurityActor.STATUS_BLOCKED,
        )
        SecurityBlock.objects.create(
            actor=actor,
            block_type=SecurityBlock.TYPE_ACCOUNT,
            value=str(self.user.id),
            status=SecurityBlock.STATUS_ACTIVE,
            blocked_at=timezone.now(),
            reason="Account block",
            metadata={"block_mode": SECURITY_BLOCK_MODE_HARD},
        )

        current_user_response = self.client.get(reverse("users_api:auth-current-user"), **self._auth())
        cart_response = self.client.get(reverse("commerce_api:cart-retrieve"), **self._auth())
        checkout_response = self.client.get(reverse("commerce_api:checkout-methods"), **self._auth())
        orders_response = self.client.get(reverse("commerce_api:order-list"), **self._auth())

        self.assertEqual(current_user_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(cart_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(checkout_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(orders_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(current_user_response.json()["code"], "security_blocked")

    def test_unblock_restores_access(self):
        block = self._create_ip_block("203.0.113.53")
        blocked_response = self.client.get(
            reverse("catalog_api:product-list"),
            HTTP_X_FORWARDED_FOR="203.0.113.53",
        )
        self.assertEqual(blocked_response.status_code, status.HTTP_403_FORBIDDEN)

        block.status = SecurityBlock.STATUS_RELEASED
        block.released_at = timezone.now()
        block.save(update_fields=("status", "released_at"))
        block.actor.status = SecurityActor.STATUS_UNBLOCKED
        block.actor.save(update_fields=("status", "updated_at"))
        touch_block_enforcement_revision()

        unblocked_response = self.client.get(
            reverse("catalog_api:product-list"),
            HTTP_X_FORWARDED_FOR="203.0.113.53",
        )
        self.assertEqual(unblocked_response.status_code, status.HTTP_200_OK)

    def test_rejected_requests_are_throttled_in_security_events(self):
        self._create_ip_block("203.0.113.54")
        endpoint = reverse("catalog_api:product-list")

        for _ in range(5):
            response = self.client.get(endpoint, HTTP_X_FORWARDED_FOR="203.0.113.54")
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        events_count = SecurityEvent.objects.filter(event_type="request_rejected_by_block").count()
        self.assertLessEqual(events_count, 1)

    def test_soft_block_blocks_auth_and_write_but_allows_catalog_read(self):
        self._create_ip_block("203.0.113.55", mode=SECURITY_BLOCK_MODE_SOFT)

        catalog_response = self.client.get(
            reverse("catalog_api:product-list"),
            HTTP_X_FORWARDED_FOR="203.0.113.55",
        )
        login_response = self.client.post(
            reverse("users_api:auth-login"),
            {"email": self.user.email, "password": "StrongPass12345"},
            format="json",
            HTTP_X_FORWARDED_FOR="203.0.113.55",
        )
        wishlist_write_response = self.client.post(
            reverse("commerce_api:wishlist-item-create"),
            {"product_id": "00000000-0000-0000-0000-000000000000"},
            format="json",
            HTTP_X_FORWARDED_FOR="203.0.113.55",
        )

        self.assertEqual(catalog_response.status_code, status.HTTP_200_OK)
        self.assertEqual(login_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(wishlist_write_response.status_code, status.HTTP_403_FORBIDDEN)
