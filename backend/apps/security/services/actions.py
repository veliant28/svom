from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.security.models import SecurityActor, SecurityBlock
from apps.security.services.audit import write_admin_event, write_audit_log
from apps.security.services.enforcement import (
    SECURITY_BLOCK_MODE_HARD,
    resolve_block_mode,
    touch_block_enforcement_revision,
)


def _require_text(value: str, field: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValidationError({field: "This field is required."})
    return normalized


def _normalize_block_mode(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in {SECURITY_BLOCK_MODE_SOFT, SECURITY_BLOCK_MODE_HARD} else SECURITY_BLOCK_MODE_HARD


@transaction.atomic
def create_manual_block(*, actor: SecurityActor, request, reason: str, mode: str | None = None) -> SecurityBlock:
    block_reason = _require_text(reason, "reason")
    normalized_mode = _normalize_block_mode(mode)
    now = timezone.now()
    block = SecurityBlock.objects.create(
        actor=actor,
        block_type=SecurityBlock.TYPE_IP,
        value=actor.source_identifier,
        reason=block_reason,
        is_automatic=False,
        blocked_by=request.user,
        blocked_at=now,
        metadata={"block_mode": normalized_mode},
    )

    old_value = {"status": actor.status, "block_count": actor.block_count}
    actor.status = SecurityActor.STATUS_BLOCKED
    actor.block_count += 1
    actor.last_blocked_at = now
    actor.save(update_fields=("status", "block_count", "last_blocked_at", "updated_at"))

    write_audit_log(
        request=request,
        action="manual_block",
        target=block,
        old_value=old_value,
        new_value={"status": actor.status, "block_count": actor.block_count},
        comment=block_reason,
    )
    write_admin_event(actor=actor, request=request, event_type="manual_block", metadata={"block_id": str(block.id), "reason": block_reason})
    touch_block_enforcement_revision()
    return block


@transaction.atomic
def release_block(*, block: SecurityBlock, request, reason: str) -> SecurityBlock:
    release_reason = _require_text(reason, "reason")
    old_value = {"status": block.status, "expires_at": block.expires_at.isoformat() if block.expires_at else None}

    block.status = SecurityBlock.STATUS_RELEASED
    block.released_by = request.user
    block.released_at = timezone.now()
    block.release_reason = release_reason
    block.save(update_fields=("status", "released_by", "released_at", "release_reason"))

    actor = block.actor
    has_active_blocks = actor.blocks.filter(status=SecurityBlock.STATUS_ACTIVE).exclude(id=block.id).exists()
    actor.status = SecurityActor.STATUS_BLOCKED if has_active_blocks else SecurityActor.STATUS_UNBLOCKED
    actor.last_unblocked_at = block.released_at
    actor.save(update_fields=("status", "last_unblocked_at", "updated_at"))

    new_value = {"status": block.status, "release_reason": release_reason}
    write_audit_log(request=request, action="release_block", target=block, old_value=old_value, new_value=new_value, comment=release_reason)
    write_admin_event(actor=actor, request=request, event_type="unblock", metadata={"block_id": str(block.id), "reason": release_reason})
    touch_block_enforcement_revision()
    return block


@transaction.atomic
def whitelist_actor(*, actor: SecurityActor, request, reason: str) -> SecurityActor:
    comment = _require_text(reason, "reason")
    old_value = {"status": actor.status}

    active_blocks = actor.blocks.filter(status=SecurityBlock.STATUS_ACTIVE)
    now = timezone.now()
    active_blocks.update(status=SecurityBlock.STATUS_RELEASED, released_by=request.user, released_at=now, release_reason=comment)

    actor.status = SecurityActor.STATUS_WHITELISTED
    actor.last_unblocked_at = now
    actor.save(update_fields=("status", "last_unblocked_at", "updated_at"))

    write_audit_log(request=request, action="whitelist_actor", target=actor, old_value=old_value, new_value={"status": actor.status}, comment=comment)
    write_admin_event(actor=actor, request=request, event_type="whitelist", metadata={"reason": comment})
    touch_block_enforcement_revision()
    return actor


@transaction.atomic
def extend_block(*, block: SecurityBlock, request, minutes: int, reason: str, mode: str | None = None) -> SecurityBlock:
    comment = _require_text(reason, "reason")
    try:
        normalized_minutes = max(1, int(minutes))
    except (TypeError, ValueError):
        raise ValidationError({"minutes": "Invalid duration."})

    old_value = {"expires_at": block.expires_at.isoformat() if block.expires_at else None}
    block.status = SecurityBlock.STATUS_ACTIVE
    block.expires_at = timezone.now() + timedelta(minutes=normalized_minutes)
    block.comment = comment
    next_mode = _normalize_block_mode(mode) if mode is not None else resolve_block_mode(block)
    block.metadata = {
        **(block.metadata if isinstance(block.metadata, dict) else {}),
        "block_mode": next_mode,
    }
    block.save(update_fields=("status", "expires_at", "comment", "metadata"))

    actor = block.actor
    actor.status = SecurityActor.STATUS_BLOCKED
    actor.last_blocked_at = timezone.now()
    actor.save(update_fields=("status", "last_blocked_at", "updated_at"))

    write_audit_log(request=request, action="extend_block", target=block, old_value=old_value, new_value={"expires_at": block.expires_at.isoformat()}, comment=comment)
    write_admin_event(actor=actor, request=request, event_type="manual_block", metadata={"block_id": str(block.id), "minutes": normalized_minutes})
    touch_block_enforcement_revision()
    return block


@transaction.atomic
def add_actor_comment(*, actor: SecurityActor, request, comment: str) -> SecurityActor:
    normalized = _require_text(comment, "comment")
    write_audit_log(request=request, action="comment_added", target=actor, old_value=None, new_value={"comment": normalized}, comment=normalized)
    write_admin_event(actor=actor, request=request, event_type="comment_added", metadata={"comment": normalized})
    return actor


@transaction.atomic
def mark_false_positive(*, actor: SecurityActor, request, reason: str) -> SecurityActor:
    comment = _require_text(reason, "reason")
    old_value = {"status": actor.status, "threat_level": actor.threat_level}

    actor.status = SecurityActor.STATUS_UNBLOCKED
    actor.threat_level = SecurityActor.THREAT_LOW
    actor.threat_score = 0
    actor.save(update_fields=("status", "threat_level", "threat_score", "updated_at"))

    write_audit_log(
        request=request,
        action="false_positive",
        target=actor,
        old_value=old_value,
        new_value={"status": actor.status, "threat_level": actor.threat_level, "threat_score": actor.threat_score},
        comment=comment,
    )
    write_admin_event(actor=actor, request=request, event_type="false_positive", metadata={"reason": comment})
    touch_block_enforcement_revision()
    return actor
