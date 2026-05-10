from __future__ import annotations

import ipaddress

from django.utils import timezone

from apps.security.models import SecurityAuditLog, SecurityEvent


def request_ip(request) -> str:
    forwarded = str(request.META.get("HTTP_X_FORWARDED_FOR", "") or "").split(",", 1)[0].strip()
    raw_ip = forwarded or str(request.META.get("REMOTE_ADDR", "") or "").strip()
    try:
        ipaddress.ip_address(raw_ip)
    except ValueError:
        return ""
    return raw_ip


def request_user_agent(request) -> str:
    return str(request.META.get("HTTP_USER_AGENT", "") or "")


def write_audit_log(*, request, action: str, target, old_value=None, new_value=None, comment: str = "") -> SecurityAuditLog:
    return SecurityAuditLog.objects.create(
        admin_user=request.user if getattr(request.user, "is_authenticated", False) else None,
        action=action,
        target_type=target.__class__.__name__,
        target_id=str(getattr(target, "id", "")),
        target_label=str(target),
        old_value=old_value,
        new_value=new_value,
        ip=request_ip(request) or None,
        user_agent=request_user_agent(request),
        comment=comment,
    )


def write_admin_event(*, actor, request, event_type: str, metadata: dict | None = None) -> SecurityEvent:
    now = timezone.now()
    actor.last_seen_at = now
    actor.save(update_fields=("last_seen_at", "updated_at"))
    return SecurityEvent.objects.create(
        actor=actor,
        event_type=event_type,
        severity=actor.threat_level,
        source_ip=actor.source_ip,
        source_kind=actor.source_kind,
        user=actor.user,
        login_snapshot=actor.login_snapshot,
        email_snapshot=actor.email_snapshot,
        user_agent=request_user_agent(request),
        metadata=metadata or {},
        actor_type=SecurityEvent.ACTOR_ADMIN,
        actor_user=request.user if getattr(request.user, "is_authenticated", False) else None,
    )
