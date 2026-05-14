from __future__ import annotations

from types import ModuleType
from typing import Callable

import inspect

_ALLOWED_CALLER_SUFFIX = "/apps/autodb/services/remote_client.py"
_ERROR_MESSAGE = (
    "Direct remote DB connection is blocked. "
    "Use AutoDbProRemoteClient service gateway."
)
_GUARD_MARKER = "__autodb_guard_wrapped__"
_ORIGINAL_MARKER = "__autodb_guard_original__"
_PATCHED = False


def enforce_remote_db_gateway() -> None:
    global _PATCHED
    if _PATCHED:
        return
    _patch_mysql_connector()
    _patch_pymysql()
    _PATCHED = True


def _patch_mysql_connector() -> None:
    try:
        import mysql.connector as mysql_connector  # type: ignore
    except Exception:  # noqa: BLE001
        return
    _patch_module_connect(mysql_connector, "connect")


def _patch_pymysql() -> None:
    try:
        import pymysql  # type: ignore
    except Exception:  # noqa: BLE001
        return
    _patch_module_connect(pymysql, "connect")


def _patch_module_connect(module: ModuleType, attr: str) -> None:
    original = getattr(module, attr, None)
    if original is None:
        return
    if bool(getattr(original, _GUARD_MARKER, False)):
        return
    guarded = _build_guarded_connect(original)
    setattr(module, attr, guarded)


def _build_guarded_connect(original: Callable):
    def guarded_connect(*args, **kwargs):
        if _stack_has_allowed_caller():
            return original(*args, **kwargs)
        raise RuntimeError(_ERROR_MESSAGE)

    setattr(guarded_connect, _GUARD_MARKER, True)
    setattr(guarded_connect, _ORIGINAL_MARKER, original)
    return guarded_connect


def _stack_has_allowed_caller(max_depth: int = 48) -> bool:
    frame = inspect.currentframe()
    if frame is None:
        return False
    current = frame.f_back
    depth = 0
    while current is not None and depth < max_depth:
        filename = str(getattr(current.f_code, "co_filename", "") or "").replace("\\", "/")
        if filename.endswith(_ALLOWED_CALLER_SUFFIX):
            return True
        current = current.f_back
        depth += 1
    return False

