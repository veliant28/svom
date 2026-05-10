from __future__ import annotations

import ipaddress

from django.utils import timezone

from apps.security.models import SecurityActor, SecurityEvent


SECURITY_STATUS_CODES = {401, 403, 429}


def _parse_ip(ip_value: str):
    try:
        return ipaddress.ip_address(ip_value)
    except ValueError:
        return None


def _source_kind(ip_value: str) -> str:
    parsed = _parse_ip(ip_value)
    if parsed is None:
        return SecurityActor.SOURCE_UNKNOWN
    return SecurityActor.SOURCE_IPV6 if parsed.version == 6 else SecurityActor.SOURCE_IPV4


def _request_ip(request) -> str:
    forwarded = str(request.META.get("HTTP_X_FORWARDED_FOR", "") or "").split(",", 1)[0].strip()
    return forwarded or str(request.META.get("REMOTE_ADDR", "") or "").strip()


def record_security_event_from_request(*, request, response) -> None:
    if str(getattr(response, "headers", {}).get("X-Security-Blocked", "") or "") == "1":
        return

    status_code = int(getattr(response, "status_code", 0) or 0)
    if status_code not in SECURITY_STATUS_CODES:
        return

    ip_value = _request_ip(request)
    if not ip_value:
        return

    now = timezone.now()
    source_kind = _source_kind(ip_value)
    source_ip = ip_value if _parse_ip(ip_value) is not None else None
    actor, _ = SecurityActor.objects.get_or_create(
        source_identifier=ip_value,
        defaults={
            "source_ip": source_ip,
            "source_kind": source_kind,
            "status": SecurityActor.STATUS_SUSPICIOUS,
            "threat_level": SecurityActor.THREAT_MEDIUM if status_code == 429 else SecurityActor.THREAT_LOW,
            "first_seen_at": now,
            "last_seen_at": now,
        },
    )
    actor.last_seen_at = now
    if not actor.source_ip:
        actor.source_ip = source_ip
    if actor.source_kind == SecurityActor.SOURCE_UNKNOWN:
        actor.source_kind = source_kind
    actor.save(update_fields=("source_ip", "source_kind", "last_seen_at", "updated_at"))

    event_type = "rate_limit_exceeded" if status_code == 429 else "auth_or_forbidden"
    SecurityEvent.objects.create(
        actor=actor,
        event_type=event_type,
        severity=actor.threat_level,
        source_ip=actor.source_ip,
        source_kind=actor.source_kind,
        user=request.user if getattr(request.user, "is_authenticated", False) else None,
        email_snapshot=getattr(request.user, "email", "") if getattr(request.user, "is_authenticated", False) else "",
        method=str(request.method or ""),
        endpoint=str(request.path or "")[:512],
        status_code=status_code,
        user_agent=str(request.META.get("HTTP_USER_AGENT", "") or ""),
        session_key=getattr(getattr(request, "session", None), "session_key", "") or "",
        actor_type=SecurityEvent.ACTOR_USER if getattr(request.user, "is_authenticated", False) else SecurityEvent.ACTOR_ANONYMOUS,
    )
