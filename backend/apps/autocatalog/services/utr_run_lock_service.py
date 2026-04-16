from __future__ import annotations

from contextlib import contextmanager
from uuid import uuid4

from django.core.cache import cache
from django.db import connections


class UtrRunLockService:
    """
    Global lock for UTR autocatalog import runs.

    PostgreSQL advisory lock is process-safe and automatically released when the
    DB session goes away, so crashed workers do not leave permanent locks.
    """

    DEFAULT_LOCK_KEY = 804_721_451
    DEFAULT_CACHE_TTL_SECONDS = 60 * 60

    def __init__(
        self,
        *,
        db_alias: str = "default",
        lock_key: int | None = None,
        cache_ttl_seconds: int | None = None,
    ):
        self.db_alias = db_alias
        self.lock_key = int(lock_key if lock_key is not None else self.DEFAULT_LOCK_KEY)
        self.cache_ttl_seconds = max(int(cache_ttl_seconds or self.DEFAULT_CACHE_TTL_SECONDS), 60)
        self._acquired = False
        self._fallback_cache_key = f"utr:import_lock:{self.lock_key}"
        self._fallback_owner_token = uuid4().hex

    def acquire(self) -> bool:
        connection = connections[self.db_alias]
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_lock(%s)", [self.lock_key])
                row = cursor.fetchone()
            self._acquired = bool(row and row[0])
            return self._acquired

        # Fallback lock for non-PostgreSQL environments.
        try:
            self._acquired = bool(
                cache.add(
                    self._fallback_cache_key,
                    self._fallback_owner_token,
                    timeout=self.cache_ttl_seconds,
                )
            )
        except Exception:
            self._acquired = False
        return self._acquired

    def release(self) -> None:
        if not self._acquired:
            return
        connection = connections[self.db_alias]
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [self.lock_key])
        else:
            try:
                owner = cache.get(self._fallback_cache_key)
                if owner == self._fallback_owner_token:
                    cache.delete(self._fallback_cache_key)
            except Exception:
                pass
        self._acquired = False

    @contextmanager
    def hold(self):
        acquired = self.acquire()
        try:
            yield acquired
        finally:
            self.release()
