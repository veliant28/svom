from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.support.models import SupportMessage, SupportThread, SupportThreadParticipantState
from apps.support.realtime.events import SupportGroups
from apps.support.realtime.publisher import publish_group_event
from apps.support.selectors import (
    build_queue_snapshot,
    build_user_counters,
    build_wallboard_snapshot,
    get_customer_thread,
    get_latest_message,
    get_staff_thread,
    serialize_message,
    serialize_thread,
    serialize_thread_base,
    serialize_user,
)
from apps.support.services.realtime_state import (
    COUNTERS_SNAPSHOT_KEY,
    QUEUE_SNAPSHOT_KEY,
    WALLBOARD_SNAPSHOT_KEY,
    get_support_redis,
    list_typing_users as list_typing_user_ids,
    set_json_snapshot,
    set_presence,
    set_typing,
)
from apps.users.rbac import user_has_capability

User = get_user_model()

SYSTEM_EVENT_ASSIGNED_MANUAL = "thread.assigned.manual"
SYSTEM_EVENT_ASSIGNED_AUTO_REPLY = "thread.assigned.auto_reply"
SYSTEM_EVENT_REASSIGNED_MANUAL = "thread.reassigned.manual"
SYSTEM_EVENT_REASSIGNED_AUTO_REPLY = "thread.reassigned.auto_reply"
SYSTEM_EVENT_STATUS_CHANGED = "thread.status_changed"

ALLOWED_STATUS_TRANSITIONS = {
    SupportThread.STATUS_NEW,
    SupportThread.STATUS_OPEN,
    SupportThread.STATUS_RESOLVED,
    SupportThread.STATUS_CLOSED,
}


def resolve_support_role(user) -> str:
    return "staff" if user_has_capability(user, "customers.support") else "customer"


def ensure_support_staff(user) -> None:
    if not user_has_capability(user, "customers.support"):
        raise ValidationError({"detail": "Support capability is required."})


def can_access_thread(*, user, thread: SupportThread) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user_has_capability(user, "customers.support"):
        return True
    return thread.customer_id == user.id


def can_access_thread_id(*, user, thread_id) -> bool:
    thread = SupportThread.objects.filter(id=thread_id).only("id", "customer_id").first()
    if thread is None:
        return False
    return can_access_thread(user=user, thread=thread)


def _validate_subject(subject: str) -> str:
    value = str(subject or "").strip()
    if not value:
        raise ValidationError({"subject": "Subject is required."})
    if len(value) > 255:
        raise ValidationError({"subject": "Subject is too long."})
    return value


def _validate_body(body: str) -> str:
    value = str(body or "").strip()
    if not value:
        raise ValidationError({"body": "Message body is required."})
    return value


def _get_or_create_state(*, thread: SupportThread, user) -> SupportThreadParticipantState:
    state, _created = SupportThreadParticipantState.objects.get_or_create(thread=thread, user=user)
    return state


def _mark_state_read(*, thread: SupportThread, user, message: SupportMessage, read_at) -> SupportThreadParticipantState:
    state = _get_or_create_state(thread=thread, user=user)
    state.last_read_message = message
    state.last_read_at = read_at
    state.unread_count = 0
    state.save(update_fields=("last_read_message", "last_read_at", "unread_count", "updated_at"))
    return state


def _set_state_unread_hint(*, thread: SupportThread, user, unread_count: int) -> SupportThreadParticipantState:
    state = _get_or_create_state(thread=thread, user=user)
    state.unread_count = max(int(unread_count or 0), 0)
    state.save(update_fields=("unread_count", "updated_at"))
    return state


def _increment_state_unread(*, thread: SupportThread, user, amount: int = 1) -> SupportThreadParticipantState:
    state = _get_or_create_state(thread=thread, user=user)
    state.unread_count = max(state.unread_count + amount, 0)
    state.save(update_fields=("unread_count", "updated_at"))
    return state


def _create_system_event(*, thread: SupportThread, event_code: str, payload: dict[str, Any], author=None) -> SupportMessage:
    return SupportMessage.objects.create(
        thread=thread,
        author=author,
        author_side=SupportMessage.SIDE_SYSTEM,
        kind=SupportMessage.KIND_SYSTEM_EVENT,
        body="",
        event_code=event_code,
        event_payload=payload,
    )


def _resolve_initial_assignee_unread(*, thread: SupportThread) -> int:
    latest_message = get_latest_message(thread_id=thread.id)
    if latest_message is None:
        return 0
    if latest_message.author_side == SupportMessage.SIDE_CUSTOMER and thread.status in {
        SupportThread.STATUS_NEW,
        SupportThread.STATUS_WAITING_FOR_SUPPORT,
        SupportThread.STATUS_OPEN,
    }:
        return 1
    return 0


def _invalidate_support_snapshots(*, user_ids: Iterable[int] = ()) -> None:
    client = get_support_redis()
    client.delete(QUEUE_SNAPSHOT_KEY)
    client.delete(WALLBOARD_SNAPSHOT_KEY)
    for user_id in {int(user_id) for user_id in user_ids if user_id}:
        client.delete(COUNTERS_SNAPSHOT_KEY.format(user_id=user_id))


def rebuild_support_wallboard_snapshots(*, user_ids: Iterable[int] = ()) -> dict[str, Any]:
    _invalidate_support_snapshots(user_ids=user_ids)
    queue_snapshot = build_queue_snapshot()
    wallboard_snapshot = build_wallboard_snapshot()
    set_json_snapshot(QUEUE_SNAPSHOT_KEY, queue_snapshot)
    set_json_snapshot(WALLBOARD_SNAPSHOT_KEY, wallboard_snapshot)
    for user_id in {int(user_id) for user_id in user_ids if user_id}:
        user = User.objects.filter(id=user_id, is_active=True).first()
        if user is None:
            continue
        set_json_snapshot(COUNTERS_SNAPSHOT_KEY.format(user_id=user_id), build_user_counters(user=user))
    return {
        "queue": queue_snapshot,
        "wallboard": wallboard_snapshot,
    }


def _publish_personal_thread_event(*, user_id: int, thread_id, event: str) -> None:
    user = User.objects.filter(id=user_id, is_active=True).first()
    if user is None:
        return

    if user_has_capability(user, "customers.support"):
        thread = get_staff_thread(user_id=user.id, thread_id=thread_id)
        group = SupportGroups.staff(user.id)
    else:
        thread = get_customer_thread(customer_id=user.id, thread_id=thread_id)
        group = SupportGroups.customer(user.id)

    if thread is None:
        return

    payload = {
        "thread": serialize_thread(thread, current_user_id=user.id),
    }
    publish_group_event(group=group, event=event, payload=payload)


def _publish_counter_event(*, user_id: int) -> None:
    user = User.objects.filter(id=user_id, is_active=True).first()
    if user is None:
        return
    payload = build_user_counters(user=user)
    group = SupportGroups.staff(user.id) if user_has_capability(user, "customers.support") else SupportGroups.customer(user.id)
    publish_group_event(group=group, event="support.counters.updated", payload=payload)


def _publish_thread_group_event(*, thread_id, event: str, payload: dict[str, Any]) -> None:
    publish_group_event(group=SupportGroups.thread(str(thread_id)), event=event, payload=payload)


def _publish_message_events(*, thread_id, messages: Iterable[SupportMessage]) -> None:
    for message in messages:
        _publish_thread_group_event(
            thread_id=thread_id,
            event="support.message.created",
            payload={
                "thread_id": str(thread_id),
                "message": serialize_message(message),
            },
        )


def _publish_queue_and_wallboard(*, snapshots: dict[str, Any]) -> None:
    publish_group_event(group=SupportGroups.queue(), event="support.queue.updated", payload=snapshots["queue"])
    publish_group_event(group=SupportGroups.wallboard(), event="support.wallboard.updated", payload=snapshots["wallboard"])


def _publish_thread_refresh(
    *,
    thread: SupportThread,
    thread_event: str,
    affected_user_ids: Iterable[int],
    messages: Iterable[SupportMessage] = (),
    extra_thread_payload: dict[str, Any] | None = None,
) -> None:
    user_ids = {int(user_id) for user_id in affected_user_ids if user_id}
    snapshots = rebuild_support_wallboard_snapshots(user_ids=user_ids)

    refreshed_thread = SupportThread.objects.select_related("customer", "assigned_staff").get(id=thread.id)
    thread_payload = {"thread": serialize_thread_base(refreshed_thread)}
    if extra_thread_payload:
        thread_payload.update(extra_thread_payload)

    _publish_thread_group_event(thread_id=thread.id, event=thread_event, payload=thread_payload)
    _publish_thread_group_event(thread_id=thread.id, event="support.thread.updated", payload=thread_payload)
    _publish_message_events(thread_id=thread.id, messages=messages)

    for user_id in user_ids:
        _publish_personal_thread_event(user_id=user_id, thread_id=thread.id, event=thread_event)
        _publish_personal_thread_event(user_id=user_id, thread_id=thread.id, event="support.thread.updated")
        _publish_counter_event(user_id=user_id)

    _publish_queue_and_wallboard(snapshots=snapshots)


def create_support_thread(*, customer, subject: str, body: str) -> tuple[SupportThread, SupportMessage]:
    normalized_subject = _validate_subject(subject)
    normalized_body = _validate_body(body)
    now = timezone.now()

    with transaction.atomic():
        thread = SupportThread.objects.create(
            subject=normalized_subject,
            customer=customer,
            status=SupportThread.STATUS_NEW,
            priority=SupportThread.PRIORITY_NORMAL,
            last_message_at=now,
        )
        message = SupportMessage.objects.create(
            thread=thread,
            author=customer,
            author_side=SupportMessage.SIDE_CUSTOMER,
            kind=SupportMessage.KIND_MESSAGE,
            body=normalized_body,
        )
        _mark_state_read(thread=thread, user=customer, message=message, read_at=message.created_at)
        transaction.on_commit(
            lambda: _publish_thread_refresh(
                thread=thread,
                thread_event="support.thread.created",
                affected_user_ids=[customer.id],
                messages=[message],
            )
        )
    return thread, message


def send_support_message(*, thread: SupportThread, author, body: str) -> list[SupportMessage]:
    normalized_body = _validate_body(body)
    if not can_access_thread(user=author, thread=thread):
        raise ValidationError({"detail": "You cannot access this thread."})

    author_side = SupportMessage.SIDE_STAFF if user_has_capability(author, "customers.support") else SupportMessage.SIDE_CUSTOMER
    if thread.status == SupportThread.STATUS_CLOSED and author_side == SupportMessage.SIDE_CUSTOMER:
        raise ValidationError({"detail": "Closed threads cannot receive new messages."})
    if author_side == SupportMessage.SIDE_CUSTOMER and thread.customer_id != author.id:
        raise ValidationError({"detail": "You cannot post into another customer's thread."})

    now = timezone.now()
    created_messages: list[SupportMessage] = []
    affected_user_ids = {thread.customer_id, author.id}
    old_assigned_staff_id = thread.assigned_staff_id
    thread_event = "support.thread.updated"
    extra_payload: dict[str, Any] = {}

    with transaction.atomic():
        if author_side == SupportMessage.SIDE_STAFF:
            ensure_support_staff(author)
            if thread.assigned_staff_id != author.id:
                if thread.assigned_staff_id is None:
                    system_message = _create_system_event(
                        thread=thread,
                        event_code=SYSTEM_EVENT_ASSIGNED_AUTO_REPLY,
                        payload={"kind": "auto_reply", "to_staff_id": author.id},
                        author=author,
                    )
                    thread_event = "support.thread.assigned"
                else:
                    system_message = _create_system_event(
                        thread=thread,
                        event_code=SYSTEM_EVENT_REASSIGNED_AUTO_REPLY,
                        payload={
                            "kind": "auto_reply",
                            "from_staff_id": thread.assigned_staff_id,
                            "to_staff_id": author.id,
                        },
                        author=author,
                    )
                    thread_event = "support.thread.reassigned"
                    affected_user_ids.add(thread.assigned_staff_id)
                created_messages.append(system_message)
                thread.assigned_staff = author
                affected_user_ids.add(author.id)
                _set_state_unread_hint(thread=thread, user=author, unread_count=0)

            if thread.first_response_at is None:
                thread.first_response_at = now
            thread.status = SupportThread.STATUS_OPEN
            thread.resolved_at = None
            thread.closed_at = None
        else:
            if thread.first_response_at is None and thread.status == SupportThread.STATUS_NEW:
                thread.status = SupportThread.STATUS_NEW
            else:
                thread.status = SupportThread.STATUS_OPEN
            thread.resolved_at = None
            thread.closed_at = None

        message = SupportMessage.objects.create(
            thread=thread,
            author=author,
            author_side=author_side,
            kind=SupportMessage.KIND_MESSAGE,
            body=normalized_body,
        )
        created_messages.append(message)

        thread.last_message_at = message.created_at
        thread.save(
            update_fields=(
                "assigned_staff",
                "status",
                "last_message_at",
                "first_response_at",
                "resolved_at",
                "closed_at",
                "updated_at",
            )
        )

        if author_side == SupportMessage.SIDE_CUSTOMER:
            _mark_state_read(thread=thread, user=author, message=message, read_at=message.created_at)
            if thread.assigned_staff_id:
                _increment_state_unread(thread=thread, user=thread.assigned_staff, amount=1)
                affected_user_ids.add(thread.assigned_staff_id)
        else:
            _mark_state_read(thread=thread, user=author, message=message, read_at=message.created_at)
            _increment_state_unread(thread=thread, user=thread.customer, amount=1)

        if old_assigned_staff_id and old_assigned_staff_id != thread.assigned_staff_id:
            affected_user_ids.add(old_assigned_staff_id)

        extra_payload = {
            "status": thread.status,
            "assigned_staff": serialize_user(thread.assigned_staff),
        }
        transaction.on_commit(
            lambda: _publish_thread_refresh(
                thread=thread,
                thread_event=thread_event,
                affected_user_ids=affected_user_ids,
                messages=created_messages,
                extra_thread_payload=extra_payload,
            )
        )

    return created_messages


def mark_support_thread_read(*, thread: SupportThread, user) -> SupportThreadParticipantState:
    if not can_access_thread(user=user, thread=thread):
        raise ValidationError({"detail": "You cannot access this thread."})

    latest_message = get_latest_message(thread_id=thread.id)
    now = timezone.now()
    with transaction.atomic():
        state = _get_or_create_state(thread=thread, user=user)
        if latest_message is not None:
            state.last_read_message = latest_message
        state.last_read_at = now
        state.unread_count = 0
        state.save(update_fields=("last_read_message", "last_read_at", "unread_count", "updated_at"))
        transaction.on_commit(
            lambda: _publish_thread_refresh(
                thread=thread,
                thread_event="support.thread.read",
                affected_user_ids=[user.id],
                extra_thread_payload={"reader_id": user.id},
            )
        )
    return state


def assign_support_thread(*, thread: SupportThread, assigned_staff, actor) -> SupportThread:
    ensure_support_staff(actor)
    ensure_support_staff(assigned_staff)

    old_assigned_staff_id = thread.assigned_staff_id
    if old_assigned_staff_id == assigned_staff.id:
        return thread

    affected_user_ids = {thread.customer_id, actor.id, assigned_staff.id}
    if old_assigned_staff_id:
        affected_user_ids.add(old_assigned_staff_id)

    with transaction.atomic():
        thread.assigned_staff = assigned_staff
        thread.save(update_fields=("assigned_staff", "updated_at"))
        _set_state_unread_hint(thread=thread, user=assigned_staff, unread_count=_resolve_initial_assignee_unread(thread=thread))
        system_message = _create_system_event(
            thread=thread,
            event_code=SYSTEM_EVENT_ASSIGNED_MANUAL if old_assigned_staff_id is None else SYSTEM_EVENT_REASSIGNED_MANUAL,
            payload={
                "kind": "manual",
                "actor_id": actor.id,
                "from_staff_id": old_assigned_staff_id,
                "to_staff_id": assigned_staff.id,
            },
            author=actor,
        )
        transaction.on_commit(
            lambda: _publish_thread_refresh(
                thread=thread,
                thread_event="support.thread.assigned" if old_assigned_staff_id is None else "support.thread.reassigned",
                affected_user_ids=affected_user_ids,
                messages=[system_message],
                extra_thread_payload={"assigned_staff": serialize_user(assigned_staff)},
            )
        )
    return thread


def change_support_thread_status(*, thread: SupportThread, status: str, actor) -> SupportThread:
    ensure_support_staff(actor)
    normalized_status = str(status or "").strip()
    if normalized_status not in ALLOWED_STATUS_TRANSITIONS:
        raise ValidationError({"status": "Unsupported status."})
    if thread.status == normalized_status:
        return thread

    now = timezone.now()
    affected_user_ids = {thread.customer_id, actor.id}
    if thread.assigned_staff_id:
        affected_user_ids.add(thread.assigned_staff_id)

    with transaction.atomic():
        thread.status = normalized_status
        if normalized_status == SupportThread.STATUS_RESOLVED:
            thread.resolved_at = now
            thread.closed_at = None
        elif normalized_status == SupportThread.STATUS_CLOSED:
            thread.closed_at = now
        else:
            thread.resolved_at = None
            thread.closed_at = None
        thread.save(update_fields=("status", "resolved_at", "closed_at", "updated_at"))
        system_message = _create_system_event(
            thread=thread,
            event_code=SYSTEM_EVENT_STATUS_CHANGED,
            payload={
                "actor_id": actor.id,
                "status": normalized_status,
            },
            author=actor,
        )
        transaction.on_commit(
            lambda: _publish_thread_refresh(
                thread=thread,
                thread_event="support.thread.status_changed",
                affected_user_ids=affected_user_ids,
                messages=[system_message],
                extra_thread_payload={"status": normalized_status},
            )
        )
    return thread


def build_typing_payload(*, thread_id) -> dict[str, Any]:
    customer_ids = list_typing_user_ids(thread_id=str(thread_id), side=SupportMessage.SIDE_CUSTOMER)
    staff_ids = list_typing_user_ids(thread_id=str(thread_id), side=SupportMessage.SIDE_STAFF)
    customer_users = {user.id: user for user in User.objects.filter(id__in=customer_ids, is_active=True)}
    staff_users = {user.id: user for user in User.objects.filter(id__in=staff_ids, is_active=True)}
    return {
        "thread_id": str(thread_id),
        "customer_users": [serialize_user(customer_users[user_id]) for user_id in customer_ids if user_id in customer_users],
        "staff_users": [serialize_user(staff_users[user_id]) for user_id in staff_ids if user_id in staff_users],
    }


def set_support_typing(*, thread: SupportThread, user, is_typing: bool) -> dict[str, Any]:
    if not can_access_thread(user=user, thread=thread):
        raise ValidationError({"detail": "You cannot access this thread."})

    side = SupportMessage.SIDE_STAFF if user_has_capability(user, "customers.support") else SupportMessage.SIDE_CUSTOMER
    set_typing(thread_id=str(thread.id), user_id=user.id, side=side, is_typing=is_typing)
    payload = build_typing_payload(thread_id=thread.id)
    publish_group_event(group=SupportGroups.thread(str(thread.id)), event="support.typing.updated", payload=payload)
    return payload


def publish_presence_state(*, user_id: int, role: str, online: bool) -> None:
    user = User.objects.filter(id=user_id, is_active=True).first()
    payload = {
        "user_id": user_id,
        "role": role,
        "online": online,
        "user": serialize_user(user) if user else {"id": user_id, "is_online": online},
    }
    publish_group_event(group=SupportGroups.queue(), event="support.presence.updated", payload=payload)
    publish_group_event(group=SupportGroups.wallboard(), event="support.presence.updated", payload=payload)

    if role == "staff":
        thread_ids = SupportThread.objects.filter(assigned_staff_id=user_id).values_list("id", flat=True)
    else:
        thread_ids = SupportThread.objects.filter(customer_id=user_id).values_list("id", flat=True)

    for thread_id in thread_ids:
        publish_group_event(
            group=SupportGroups.thread(str(thread_id)),
            event="support.presence.updated",
            payload={"thread_id": str(thread_id), **payload},
        )


def touch_support_presence(*, user) -> bool:
    role = resolve_support_role(user)
    changed = set_presence(user_id=user.id, role=role)
    if changed:
        transaction.on_commit(lambda: publish_presence_state(user_id=user.id, role=role, online=True))
    return changed
