from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, DurationField, F, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.support.models import SupportMessage, SupportThread, SupportThreadParticipantState
from apps.support.services.realtime_state import (
    COUNTERS_SNAPSHOT_KEY,
    QUEUE_SNAPSHOT_KEY,
    WALLBOARD_SNAPSHOT_KEY,
    get_json_snapshot,
    is_user_online,
)
from apps.users.rbac import user_has_capability

User = get_user_model()

WAITING_STATUSES = (
    SupportThread.STATUS_NEW,
)

ACTIVE_STATUSES = (
    SupportThread.STATUS_NEW,
    SupportThread.STATUS_OPEN,
    SupportThread.STATUS_WAITING_FOR_SUPPORT,
    SupportThread.STATUS_WAITING_FOR_CLIENT,
)

LEGACY_WAITING_STATUSES = (
    SupportThread.STATUS_WAITING_FOR_SUPPORT,
    SupportThread.STATUS_WAITING_FOR_CLIENT,
)


@dataclass(frozen=True)
class SupportThreadFilters:
    status: str = ""
    assigned_to_me: bool = False
    unassigned: bool = False
    waiting: bool = False
    search: str = ""
    ordering: str = "-last_message_at"


def _participant_unread_subquery(*, user_id: int):
    return SupportThreadParticipantState.objects.filter(thread_id=OuterRef("pk"), user_id=user_id).values("unread_count")[:1]


def _base_queryset(*, user_id: int):
    return SupportThread.objects.select_related("customer", "assigned_staff").annotate(
        participant_unread_count=Coalesce(Subquery(_participant_unread_subquery(user_id=user_id)), Value(0)),
    )


def normalize_public_thread_status(status: str) -> str:
    normalized = str(status or "").strip()
    if normalized in LEGACY_WAITING_STATUSES:
        return SupportThread.STATUS_OPEN
    return normalized


def _apply_common_filters(queryset, filters: SupportThreadFilters):
    result = queryset
    if filters.status:
        if filters.status == SupportThread.STATUS_OPEN:
            result = result.filter(status__in=(SupportThread.STATUS_OPEN, *LEGACY_WAITING_STATUSES))
        else:
            result = result.filter(status=filters.status)
    if filters.waiting:
        result = result.filter(status__in=WAITING_STATUSES)

    search = filters.search.strip()
    if search:
        result = result.filter(
            Q(subject__icontains=search)
            | Q(customer__email__icontains=search)
            | Q(customer__first_name__icontains=search)
            | Q(customer__last_name__icontains=search)
            | Q(id__icontains=search)
        )

    ordering = filters.ordering if filters.ordering in {"last_message_at", "-last_message_at", "created_at", "-created_at", "priority", "-priority"} else "-last_message_at"
    return result.order_by(ordering, "-created_at")


def list_customer_threads(*, customer_id: int, filters: SupportThreadFilters):
    queryset = _base_queryset(user_id=customer_id).filter(customer_id=customer_id)
    return _apply_common_filters(queryset, filters)


def list_staff_threads(*, user_id: int, filters: SupportThreadFilters):
    queryset = _base_queryset(user_id=user_id)
    if filters.assigned_to_me:
        queryset = queryset.filter(assigned_staff_id=user_id)
    if filters.unassigned:
        queryset = queryset.filter(assigned_staff__isnull=True)
    return _apply_common_filters(queryset, filters)


def get_customer_thread(*, customer_id: int, thread_id):
    return _base_queryset(user_id=customer_id).filter(customer_id=customer_id, id=thread_id).first()


def get_staff_thread(*, user_id: int, thread_id):
    return _base_queryset(user_id=user_id).filter(id=thread_id).first()


def list_thread_messages(*, thread_id):
    return SupportMessage.objects.filter(thread_id=thread_id).select_related("author").order_by("created_at", "id")


def get_thread_messages_page(*, thread_id, before_message_id=None):
    queryset = list_thread_messages(thread_id=thread_id)
    if before_message_id:
        pivot = queryset.filter(id=before_message_id).values_list("created_at", flat=True).first()
        if pivot is not None:
            queryset = queryset.filter(created_at__lt=pivot)
    return queryset


def get_latest_message(*, thread_id):
    return SupportMessage.objects.filter(thread_id=thread_id).select_related("author").order_by("-created_at", "-id").first()


def get_participant_state(*, thread_id, user_id: int):
    return SupportThreadParticipantState.objects.filter(thread_id=thread_id, user_id=user_id).select_related("last_read_message").first()


def list_support_staff_users() -> list[User]:
    return [
        user
        for user in User.objects.filter(is_active=True).order_by("first_name", "last_name", "email")
        if user_has_capability(user, "customers.support")
    ]


def serialize_user(user: User | None) -> dict | None:
    if user is None:
        return None
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.get_full_name() or user.email,
        "is_online": is_user_online(user.id),
    }


def serialize_thread_base(thread: SupportThread) -> dict:
    latest_message = get_latest_message(thread_id=thread.id)
    public_status = normalize_public_thread_status(thread.status)
    return {
        "id": thread.id,
        "subject": thread.subject,
        "status": public_status,
        "priority": thread.priority,
        "customer": serialize_user(thread.customer),
        "assigned_staff": serialize_user(thread.assigned_staff),
        "created_at": thread.created_at,
        "updated_at": thread.updated_at,
        "last_message_at": thread.last_message_at,
        "first_response_at": thread.first_response_at,
        "resolved_at": thread.resolved_at,
        "closed_at": thread.closed_at,
        "latest_message_id": latest_message.id if latest_message else None,
        "latest_message_preview": (latest_message.body or "").strip()[:160] if latest_message else "",
        "latest_message_author_side": latest_message.author_side if latest_message else "",
        "is_waiting": public_status == SupportThread.STATUS_NEW,
    }


def serialize_thread(thread: SupportThread, *, current_user_id: int) -> dict:
    payload = serialize_thread_base(thread)
    payload.update(
        {
            "unread_count": int(getattr(thread, "participant_unread_count", 0) or 0),
            "is_mine": thread.assigned_staff_id == current_user_id,
        }
    )
    return payload


def serialize_message(message: SupportMessage) -> dict:
    return {
        "id": message.id,
        "thread_id": message.thread_id,
        "author": serialize_user(message.author),
        "author_side": message.author_side,
        "kind": message.kind,
        "body": message.body,
        "event_code": message.event_code,
        "event_payload": message.event_payload,
        "created_at": message.created_at,
        "edited_at": message.edited_at,
    }


def build_user_counters(*, user: User) -> dict:
    cached = get_json_snapshot(COUNTERS_SNAPSHOT_KEY.format(user_id=user.id))
    if cached:
        return cached

    unread_threads = SupportThreadParticipantState.objects.filter(user_id=user.id, unread_count__gt=0).count()
    payload = {
        "user_id": user.id,
        "total_unread_threads": unread_threads,
    }
    if user_has_capability(user, "customers.support"):
        payload.update(
            {
                "assigned_to_me": SupportThread.objects.filter(assigned_staff_id=user.id, status__in=ACTIVE_STATUSES).count(),
                "unassigned": SupportThread.objects.filter(assigned_staff__isnull=True, status__in=WAITING_STATUSES).count(),
            }
        )
    else:
        payload.update(
            {
                "open_threads": SupportThread.objects.filter(customer_id=user.id).exclude(status=SupportThread.STATUS_CLOSED).count(),
            }
        )
    return payload


def build_queue_snapshot() -> dict:
    cached = get_json_snapshot(QUEUE_SNAPSHOT_KEY)
    if cached:
        return cached

    newest_threads = [
        serialize_thread_base(thread)
        for thread in SupportThread.objects.select_related("customer", "assigned_staff").order_by("-last_message_at", "-created_at")[:12]
    ]
    open_count = SupportThread.objects.filter(status__in=(SupportThread.STATUS_OPEN, *LEGACY_WAITING_STATUSES)).count()
    return {
        "new": SupportThread.objects.filter(status=SupportThread.STATUS_NEW).count(),
        "open": open_count,
        "waiting_for_support": 0,
        "waiting_for_client": 0,
        "resolved": SupportThread.objects.filter(status=SupportThread.STATUS_RESOLVED).count(),
        "closed": SupportThread.objects.filter(status=SupportThread.STATUS_CLOSED).count(),
        "unassigned": SupportThread.objects.filter(assigned_staff__isnull=True).exclude(status=SupportThread.STATUS_CLOSED).count(),
        "latest_threads": newest_threads,
    }


def _avg_first_response_seconds() -> int | None:
    delta = SupportThread.objects.filter(first_response_at__isnull=False).annotate(
        first_response_delta=Coalesce(
            F("first_response_at") - F("created_at"),
            Value(timedelta(0)),
            output_field=DurationField(),
        )
    ).aggregate(avg=Avg("first_response_delta"))["avg"]
    if delta is None:
        return None
    return max(int(delta.total_seconds()), 0)


def build_wallboard_snapshot() -> dict:
    cached = get_json_snapshot(WALLBOARD_SNAPSHOT_KEY)
    if cached:
        return cached

    operator_rows = []
    support_users = list_support_staff_users()
    for user in support_users:
        operator_rows.append(
            {
                "user": serialize_user(user),
                "active_threads": SupportThread.objects.filter(assigned_staff_id=user.id).exclude(status=SupportThread.STATUS_CLOSED).count(),
            }
        )

    oldest_waiting = SupportThread.objects.filter(status__in=WAITING_STATUSES).order_by("last_message_at", "created_at").first()
    latest_active_threads = [
        serialize_thread_base(thread)
        for thread in SupportThread.objects.select_related("customer", "assigned_staff").order_by("-last_message_at", "-created_at")[:8]
    ]

    open_count = SupportThread.objects.filter(status__in=(SupportThread.STATUS_OPEN, *LEGACY_WAITING_STATUSES)).count()
    return {
        "counts": {
            "new": SupportThread.objects.filter(status=SupportThread.STATUS_NEW).count(),
            "open": open_count,
            "waiting_for_support": 0,
            "waiting_for_client": 0,
            "resolved": SupportThread.objects.filter(status=SupportThread.STATUS_RESOLVED).count(),
            "closed": SupportThread.objects.filter(status=SupportThread.STATUS_CLOSED).count(),
            "unassigned": SupportThread.objects.filter(assigned_staff__isnull=True).exclude(status=SupportThread.STATUS_CLOSED).count(),
            "online_operators": sum(1 for user in support_users if is_user_online(user.id)),
            "active_threads": SupportThread.objects.exclude(status__in=(SupportThread.STATUS_RESOLVED, SupportThread.STATUS_CLOSED)).count(),
        },
        "threads_per_operator": operator_rows,
        "oldest_waiting": serialize_thread_base(oldest_waiting) if oldest_waiting else None,
        "latest_active_threads": latest_active_threads,
        "avg_first_response_seconds": _avg_first_response_seconds(),
    }
