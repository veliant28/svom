from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from apps.supplier_imports.models import SupplierIntegration


@dataclass(frozen=True)
class StoredTokenPayload:
    access_token: str
    refresh_token: str
    access_token_expires_at: object | None
    refresh_token_expires_at: object | None


class SupplierTokenStorageService:
    def update_credentials(
        self,
        *,
        integration: SupplierIntegration,
        login: str,
        password: str,
        browser_fingerprint: str | None = None,
    ) -> SupplierIntegration:
        integration.login = login
        integration.password = password
        if browser_fingerprint is not None:
            integration.browser_fingerprint = browser_fingerprint
        integration.credentials_updated_at = timezone.now()
        integration.save(
            update_fields=(
                "login",
                "password",
                "browser_fingerprint",
                "credentials_updated_at",
                "updated_at",
            )
        )
        return integration

    def store_tokens(
        self,
        *,
        integration: SupplierIntegration,
        access_token: str,
        refresh_token: str,
        access_expires_in_seconds: int | None = None,
        refresh_expires_in_seconds: int | None = None,
        access_expires_at=None,
        refresh_expires_at=None,
        refreshed: bool = False,
    ) -> StoredTokenPayload:
        now = timezone.now()

        resolved_access_expires_at = access_expires_at
        if resolved_access_expires_at is None and access_expires_in_seconds:
            resolved_access_expires_at = now + timedelta(seconds=int(access_expires_in_seconds))

        resolved_refresh_expires_at = refresh_expires_at
        if resolved_refresh_expires_at is None and refresh_expires_in_seconds:
            resolved_refresh_expires_at = now + timedelta(seconds=int(refresh_expires_in_seconds))

        integration.access_token = access_token
        integration.refresh_token = refresh_token
        integration.access_token_expires_at = resolved_access_expires_at
        integration.refresh_token_expires_at = resolved_refresh_expires_at
        integration.token_obtained_at = now
        integration.last_token_error_at = None
        integration.last_token_error_message = ""
        if refreshed:
            integration.last_token_refresh_at = now

        integration.save(
            update_fields=(
                "access_token",
                "refresh_token",
                "access_token_expires_at",
                "refresh_token_expires_at",
                "token_obtained_at",
                "last_token_refresh_at",
                "last_token_error_at",
                "last_token_error_message",
                "updated_at",
            )
        )
        return StoredTokenPayload(
            access_token=integration.access_token,
            refresh_token=integration.refresh_token,
            access_token_expires_at=integration.access_token_expires_at,
            refresh_token_expires_at=integration.refresh_token_expires_at,
        )

    def mark_token_error(self, *, integration: SupplierIntegration, message: str) -> None:
        integration.last_token_error_at = timezone.now()
        integration.last_token_error_message = message[:2000]
        integration.save(update_fields=("last_token_error_at", "last_token_error_message", "updated_at"))

    def clear_tokens(self, *, integration: SupplierIntegration) -> None:
        integration.access_token = ""
        integration.refresh_token = ""
        integration.access_token_expires_at = None
        integration.refresh_token_expires_at = None
        integration.save(
            update_fields=(
                "access_token",
                "refresh_token",
                "access_token_expires_at",
                "refresh_token_expires_at",
                "updated_at",
            )
        )
