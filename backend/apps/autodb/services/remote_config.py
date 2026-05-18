from __future__ import annotations

from dataclasses import dataclass
import getpass

from django.conf import settings

from apps.autodb.selectors.remote_settings import get_autodb_remote_settings, has_autodb_remote_settings_table


class AutoDbRemoteConfigError(RuntimeError):
    """Raised when remote Auto_DB_Pro config is required but invalid."""


@dataclass(frozen=True)
class AutoDbRemoteConfigSnapshot:
    enabled: bool
    host: str
    port: int
    database: str
    user: str
    password: str
    connect_timeout: int
    read_timeout: int
    batch_size: int

    @property
    def password_set(self) -> bool:
        return bool(self.password)

    def os_user_fallback_risk(self) -> bool:
        local_user = str(getpass.getuser() or "").strip()
        remote_user = str(self.user or "").strip()
        return bool(remote_user and local_user and remote_user.lower() == local_user.lower())

    def validation_errors(self, *, require_enabled: bool) -> list[str]:
        errors: list[str] = []
        if require_enabled and not self.enabled:
            errors.append("AUTODB_PRO_REMOTE_ENABLED is false")
            return errors
        if not self.enabled:
            return errors

        if not self.host:
            errors.append("AUTODB_PRO_REMOTE_HOST is empty")
        if not self.database:
            errors.append("AUTODB_PRO_REMOTE_DATABASE is empty")
        if not self.user:
            errors.append("AUTODB_PRO_REMOTE_USER is empty")
        if not self.password:
            errors.append("AUTODB_PRO_REMOTE_PASSWORD is empty")
        return errors

    def sanitized(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "password_set": self.password_set,
            "connect_timeout": self.connect_timeout,
            "read_timeout": self.read_timeout,
            "batch_size": self.batch_size,
        }


class AutoDbRemoteConfigValidator:
    @classmethod
    def snapshot(cls) -> AutoDbRemoteConfigSnapshot:
        host = ""
        port = 3306
        database = ""
        user = ""
        password = ""
        if has_autodb_remote_settings_table():
            db_settings = get_autodb_remote_settings()
            host = str(db_settings.remote_host or "").strip()
            port = max(int(db_settings.remote_port or 3306), 1)
            database = str(db_settings.remote_database or "").strip()
            user = str(db_settings.remote_user or "").strip()
            password = str(db_settings.remote_password or "")

        return AutoDbRemoteConfigSnapshot(
            enabled=bool(getattr(settings, "AUTODB_PRO_REMOTE_ENABLED", False)),
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            connect_timeout=max(int(getattr(settings, "AUTODB_PRO_REMOTE_CONNECT_TIMEOUT", 10) or 10), 1),
            read_timeout=max(int(getattr(settings, "AUTODB_PRO_REMOTE_READ_TIMEOUT", 30) or 30), 1),
            batch_size=max(int(getattr(settings, "AUTODB_PRO_REMOTE_BATCH_SIZE", 100) or 100), 1),
        )

    @classmethod
    def ensure_remote_ready(cls, *, allow_remote: bool) -> AutoDbRemoteConfigSnapshot:
        snapshot = cls.snapshot()
        if not allow_remote:
            return snapshot

        errors = snapshot.validation_errors(require_enabled=True)
        if errors:
            raise AutoDbRemoteConfigError(
                "Remote Auto-DB Pro is requested but config is invalid: " + "; ".join(errors)
            )
        return snapshot
