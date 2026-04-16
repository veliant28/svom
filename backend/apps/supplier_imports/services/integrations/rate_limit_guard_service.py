from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.supplier_imports.models import SupplierIntegration
from apps.supplier_imports.services.integrations.exceptions import SupplierCooldownError


@dataclass(frozen=True)
class CooldownStatus:
    can_run: bool
    wait_seconds: int
    cooldown_seconds: int
    last_request_at: object | None
    next_allowed_request_at: object | None


class SupplierRateLimitGuardService:
    UTR_COOLDOWN_SECONDS = 60

    def get_cooldown_seconds(self, *, integration: SupplierIntegration) -> int:
        if integration.supplier.code == "utr":
            return self.UTR_COOLDOWN_SECONDS
        return 0

    def get_status(self, *, integration: SupplierIntegration) -> CooldownStatus:
        now = timezone.now()
        cooldown_seconds = self.get_cooldown_seconds(integration=integration)
        wait_seconds = 0
        if cooldown_seconds and integration.next_allowed_request_at and integration.next_allowed_request_at > now:
            wait_seconds = int((integration.next_allowed_request_at - now).total_seconds())
            if wait_seconds < 1:
                wait_seconds = 1
        return CooldownStatus(
            can_run=wait_seconds == 0,
            wait_seconds=wait_seconds,
            cooldown_seconds=cooldown_seconds,
            last_request_at=integration.last_request_at,
            next_allowed_request_at=integration.next_allowed_request_at,
        )

    def acquire_or_raise(self, *, integration_id: str, action_key: str = "") -> SupplierIntegration:
        del action_key

        with transaction.atomic():
            # Keep the locking query join-free: PostgreSQL cannot apply FOR UPDATE
            # to the nullable side of an outer join (SupplierIntegration.source is nullable).
            integration = SupplierIntegration.objects.select_for_update().order_by().get(id=integration_id)
            now = timezone.now()
            cooldown_seconds = self.get_cooldown_seconds(integration=integration)

            if cooldown_seconds and integration.next_allowed_request_at and integration.next_allowed_request_at > now:
                wait_seconds = int((integration.next_allowed_request_at - now).total_seconds())
                if wait_seconds < 1:
                    wait_seconds = 1
                raise SupplierCooldownError(retry_after_seconds=wait_seconds)

            integration.last_request_at = now
            if cooldown_seconds:
                integration.next_allowed_request_at = now + timedelta(seconds=cooldown_seconds)
            else:
                integration.next_allowed_request_at = None
            integration.save(update_fields=("last_request_at", "next_allowed_request_at", "updated_at"))
            return integration
