from __future__ import annotations

from celery import shared_task

from apps.support.services.realtime_state import take_expired_presence
from apps.support.services.support_service import publish_presence_state, rebuild_support_wallboard_snapshots


@shared_task(name="support.reconcile_presence")
def reconcile_support_presence() -> None:
    for row in take_expired_presence():
        publish_presence_state(user_id=int(row["user_id"]), role=str(row.get("role") or "unknown"), online=False)


@shared_task(name="support.rebuild_wallboard_snapshots")
def rebuild_support_wallboard_snapshots_task() -> None:
    rebuild_support_wallboard_snapshots()
