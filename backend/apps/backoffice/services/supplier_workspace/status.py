from __future__ import annotations

from django.utils import timezone


def resolve_connection_status(*, integration) -> str:
    if integration.last_connection_status:
        return integration.last_connection_status

    if integration.access_token and integration.access_token_expires_at and integration.access_token_expires_at <= timezone.now():
        return "expired"
    if integration.access_token:
        return "connected"
    if integration.last_token_error_message:
        return "error"
    return "disconnected"


def cooldown_status_label(*, can_run: bool, wait_seconds: int) -> str:
    return "Можно запускать" if can_run else f"Подождите {wait_seconds} сек."
