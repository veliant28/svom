from __future__ import annotations

_SUPPORT_EXPORTS = {
    "assign_support_thread",
    "build_typing_payload",
    "can_access_thread",
    "can_access_thread_id",
    "change_support_thread_status",
    "create_support_thread",
    "ensure_support_staff",
    "mark_support_thread_read",
    "publish_presence_state",
    "rebuild_support_wallboard_snapshots",
    "resolve_support_role",
    "send_support_message",
    "set_support_typing",
    "touch_support_presence",
}

__all__ = sorted(_SUPPORT_EXPORTS)


def __getattr__(name: str):
    if name in _SUPPORT_EXPORTS:
        from . import support_service

        return getattr(support_service, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
