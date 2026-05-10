from __future__ import annotations

from collections import Counter
from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncHour
from django.utils import timezone

from apps.security.models import SecurityActor, SecurityAuditLog, SecurityBlock, SecurityEvent


def _active_block_q():
    now = timezone.now()
    return Q(status=SecurityBlock.STATUS_ACTIVE) & (Q(expires_at__isnull=True) | Q(expires_at__gt=now))


def list_security_actors(*, query: str = "", status: str = "", threat_level: str = ""):
    qs = (
        SecurityActor.objects.select_related("user")
        .prefetch_related("blocks")
        .order_by("-last_seen_at", "-updated_at")
    )
    if query:
        qs = qs.filter(
            Q(source_identifier__icontains=query)
            | Q(email_snapshot__icontains=query)
            | Q(login_snapshot__icontains=query)
            | Q(metadata__phone__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__email__icontains=query)
            | Q(user__phone__icontains=query)
        )
    if status:
        qs = qs.filter(status=status)
    if threat_level:
        qs = qs.filter(threat_level=threat_level)
    return qs


def list_security_blocks():
    return SecurityBlock.objects.select_related("actor", "blocked_by", "released_by").order_by("-blocked_at")


def list_security_actor_history(*, actor_id, limit: int = 100):
    return SecurityEvent.objects.select_related("actor", "user", "actor_user").filter(actor_id=actor_id).order_by("-created_at")[:limit]


def list_security_audit_logs(*, limit: int = 100):
    return SecurityAuditLog.objects.select_related("admin_user").order_by("-created_at")[:limit]


def get_security_actor_detail(*, actor_id):
    actor = SecurityActor.objects.select_related("user").prefetch_related("blocks").get(id=actor_id)
    events = list(SecurityEvent.objects.filter(actor=actor).order_by("-created_at")[:10])
    active_block = actor.blocks.filter(_active_block_q()).order_by("-blocked_at").first()
    since_5m = timezone.now() - timedelta(minutes=5)
    since_1h = timezone.now() - timedelta(hours=1)
    since_24h = timezone.now() - timedelta(hours=24)
    actor_events = SecurityEvent.objects.filter(actor=actor)
    activity_summary = {
        "requests_5m": actor_events.filter(created_at__gte=since_5m).count(),
        "requests_1h": actor_events.filter(created_at__gte=since_1h).count(),
        "requests_24h": actor_events.filter(created_at__gte=since_24h).count(),
        "status_429": actor_events.filter(status_code=429, created_at__gte=since_24h).count(),
        "status_403": actor_events.filter(status_code=403, created_at__gte=since_24h).count(),
        "status_401": actor_events.filter(status_code=401, created_at__gte=since_24h).count(),
        "status_500": actor_events.filter(status_code=500, created_at__gte=since_24h).count(),
        "failed_login": actor_events.filter(event_type="failed_login", created_at__gte=since_24h).count(),
        "password_reset": actor_events.filter(event_type="password_reset_abuse", created_at__gte=since_24h).count(),
        "checkout": actor_events.filter(event_type="checkout_abuse", created_at__gte=since_24h).count(),
    }
    endpoint_counter: Counter[tuple[str, int | None]] = Counter()
    for event in SecurityEvent.objects.filter(actor=actor).exclude(endpoint="").order_by("-created_at")[:250]:
        endpoint_counter[(event.endpoint, event.status_code)] += 1
    top_endpoints = [
        {"endpoint": endpoint, "requests": count, "last_status_code": status_code}
        for (endpoint, status_code), count in endpoint_counter.most_common(8)
    ]
    return {
        "actor": actor,
        "active_block": active_block,
        "activity_summary": activity_summary,
        "recent_events": events,
        "top_endpoints": top_endpoints,
    }


def security_summary() -> dict:
    now = timezone.now()
    since_24h = now - timedelta(hours=24)
    active_blocks = SecurityBlock.objects.filter(_active_block_q()).count()
    return {
        "active_blocks": active_blocks,
        "suspicious_sources": SecurityActor.objects.filter(status=SecurityActor.STATUS_SUSPICIOUS).count(),
        "blocked_24h": SecurityBlock.objects.filter(blocked_at__gte=since_24h).count(),
        "failed_logins": SecurityEvent.objects.filter(event_type="failed_login", created_at__gte=since_24h).count(),
        "rate_limit_events": SecurityEvent.objects.filter(status_code=429, created_at__gte=since_24h).count(),
        "critical_threats": SecurityActor.objects.filter(threat_level=SecurityActor.THREAT_CRITICAL).count(),
        "latest_critical_events": SecurityEvent.objects.filter(severity=SecurityActor.THREAT_CRITICAL).order_by("-created_at")[:6],
        "active_block_rows": SecurityBlock.objects.filter(_active_block_q()).select_related("actor").order_by("expires_at")[:6],
    }


def security_timeseries() -> dict:
    since = timezone.now() - timedelta(hours=24)
    buckets = (
        SecurityEvent.objects.filter(created_at__gte=since)
        .annotate(bucket=TruncHour("created_at"))
        .values("bucket")
        .annotate(total=Count("id"))
        .order_by("bucket")
    )
    event_types = SecurityEvent.objects.filter(created_at__gte=since).values("event_type").annotate(total=Count("id")).order_by("-total")[:8]
    top_sources = SecurityEvent.objects.filter(created_at__gte=since).values("source_ip").annotate(total=Count("id")).order_by("-total")[:8]
    top_endpoints = SecurityEvent.objects.filter(created_at__gte=since).exclude(endpoint="").values("endpoint").annotate(total=Count("id")).order_by("-total")[:8]
    return {
        "events_by_hour": list(buckets),
        "events_by_type": list(event_types),
        "top_sources": list(top_sources),
        "top_endpoints": list(top_endpoints),
    }
