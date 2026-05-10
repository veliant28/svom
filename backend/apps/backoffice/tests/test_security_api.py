from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.backoffice.permissions.capability_rules import resolve_required_capabilities_for_request
from apps.security.models import SecurityActor, SecurityAuditLog, SecurityBlock, SecurityEvent
from apps.users.models import User
from apps.users.rbac import replace_group_capabilities, set_user_system_role


class BackofficeSecurityAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin-security@test.local",
            first_name="Admin",
            password="pass12345",
            is_staff=True,
        )
        self.manager = User.objects.create_user(
            email="manager-security@test.local",
            first_name="Manager",
            password="pass12345",
            is_staff=True,
        )
        self.viewer = User.objects.create_user(
            email="viewer-security@test.local",
            first_name="Viewer",
            password="pass12345",
            is_staff=True,
        )
        set_user_system_role(user=self.admin, role_code="administrator")
        set_user_system_role(user=self.manager, role_code="manager")
        set_user_system_role(user=self.viewer, role_code="manager")

        viewer_group = Group.objects.create(name="Security viewers")
        replace_group_capabilities(group=viewer_group, capability_codes=["security.view"])
        self.viewer.groups.add(viewer_group)

        self.admin_token = Token.objects.create(user=self.admin)
        self.manager_token = Token.objects.create(user=self.manager)
        self.viewer_token = Token.objects.create(user=self.viewer)

        now = timezone.now()
        self.actor = SecurityActor.objects.create(
            source_ip="192.168.1.25",
            source_identifier="192.168.1.25",
            source_kind=SecurityActor.SOURCE_IPV4,
            threat_level=SecurityActor.THREAT_CRITICAL,
            threat_score=92,
            status=SecurityActor.STATUS_BLOCKED,
            block_count=1,
            first_seen_at=now - timedelta(hours=2),
            last_seen_at=now,
            last_blocked_at=now - timedelta(minutes=30),
            metadata={"source_flags": ["vpn", "bot"], "threat_reasons": ["rate limit"]},
        )
        self.block = SecurityBlock.objects.create(
            actor=self.actor,
            value=self.actor.source_identifier,
            reason="rate limit",
            blocked_at=now - timedelta(minutes=30),
            expires_at=now + timedelta(hours=1),
        )
        SecurityEvent.objects.create(
            actor=self.actor,
            event_type="rate_limit_exceeded",
            severity=SecurityActor.THREAT_CRITICAL,
            source_ip=self.actor.source_ip,
            source_kind=self.actor.source_kind,
            method="GET",
            endpoint="/api/products/",
            status_code=429,
            user_agent="test-agent",
        )

    def _auth(self, token: Token) -> dict[str, str]:
        return {"HTTP_AUTHORIZATION": f"Token {token.key}"}

    def test_security_capability_rules(self):
        self.assertEqual(resolve_required_capabilities_for_request("/api/backoffice/security/actors/", "GET"), ("security.view",))
        self.assertEqual(resolve_required_capabilities_for_request("/api/backoffice/security/blocks/", "POST"), ("security.respond",))
        self.assertEqual(resolve_required_capabilities_for_request("/api/backoffice/security/audit/", "GET"), ("security.audit",))

    def test_actor_list_is_available_for_administrator(self):
        response = self.client.get(reverse("backoffice_api:security-actor-list"), **self._auth(self.admin_token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        row = response.data["results"][0]
        self.assertEqual(row["source_identifier"], self.actor.source_identifier)
        self.assertEqual(row["status"], SecurityActor.STATUS_BLOCKED)
        self.assertEqual(row["threat_level"], SecurityActor.THREAT_CRITICAL)
        self.assertEqual(row["active_block"]["id"], str(self.block.id))

    def test_details_and_history_api(self):
        detail_response = self.client.get(
            reverse("backoffice_api:security-actor-detail", kwargs={"id": self.actor.id}),
            **self._auth(self.admin_token),
        )
        history_response = self.client.get(
            reverse("backoffice_api:security-actor-history", kwargs={"id": self.actor.id}),
            **self._auth(self.admin_token),
        )

        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertIn("activity_summary", detail_response.data)
        self.assertEqual(detail_response.data["actor"]["source_identifier"], self.actor.source_identifier)
        self.assertEqual(history_response.status_code, status.HTTP_200_OK)
        self.assertEqual(history_response.data["results"][0]["event_type"], "rate_limit_exceeded")

    def test_release_block_writes_audit_and_event(self):
        response = self.client.post(
            reverse("backoffice_api:security-block-release", kwargs={"id": self.block.id}),
            {"reason": "manual review"},
            format="json",
            **self._auth(self.admin_token),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.block.refresh_from_db()
        self.actor.refresh_from_db()
        self.assertEqual(self.block.status, SecurityBlock.STATUS_RELEASED)
        self.assertEqual(self.block.release_reason, "manual review")
        self.assertEqual(self.actor.status, SecurityActor.STATUS_UNBLOCKED)
        self.assertTrue(SecurityAuditLog.objects.filter(action="release_block", target_id=str(self.block.id)).exists())
        self.assertTrue(SecurityEvent.objects.filter(actor=self.actor, event_type="unblock").exists())

    def test_user_without_security_view_cannot_access_security(self):
        response = self.client.get(reverse("backoffice_api:security-actor-list"), **self._auth(self.manager_token))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_without_security_respond_cannot_release_block(self):
        response = self.client.post(
            reverse("backoffice_api:security-block-release", kwargs={"id": self.block.id}),
            {"reason": "manual review"},
            format="json",
            **self._auth(self.viewer_token),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_actor_list_search_matches_source_client_email_and_phone(self):
        customer = User.objects.create_user(
            email="customer.search@test.local",
            first_name="Searchable",
            last_name="Customer",
            phone="38(067)123-45-67",
            password="pass12345",
        )
        self.actor.user = customer
        self.actor.login_snapshot = "search-login"
        self.actor.email_snapshot = "snapshot.search@test.local"
        self.actor.metadata = {"phone": "38(067)123-45-67"}
        self.actor.save(update_fields=("user", "login_snapshot", "email_snapshot", "metadata", "updated_at"))

        checks = [
            "192.168.1.25",
            "Searchable",
            "snapshot.search@test.local",
            "38(067)123-45-67",
        ]
        for query in checks:
            response = self.client.get(
                reverse("backoffice_api:security-actor-list"),
                {"q": query},
                **self._auth(self.admin_token),
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["count"], 1)
