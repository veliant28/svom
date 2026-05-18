from __future__ import annotations

from django.db import connections, router, transaction

from apps.autodb.models import AutoDbRemoteSettings


_AUTODB_REMOTE_SETTINGS_TABLE = AutoDbRemoteSettings._meta.db_table


def _remote_settings_db_alias() -> str:
    alias = router.db_for_read(AutoDbRemoteSettings)
    return str(alias or "default")


def has_autodb_remote_settings_table() -> bool:
    db_alias = _remote_settings_db_alias()
    connection = connections[db_alias]
    with connection.cursor() as cursor:
        table_names = connection.introspection.table_names(cursor)
    return _AUTODB_REMOTE_SETTINGS_TABLE in set(table_names)


@transaction.atomic
def get_autodb_remote_settings() -> AutoDbRemoteSettings:
    settings, _created = AutoDbRemoteSettings.objects.get_or_create(
        code=AutoDbRemoteSettings.DEFAULT_CODE,
    )
    return settings


def get_autodb_image_base_url() -> str:
    if not has_autodb_remote_settings_table():
        return ""
    settings = get_autodb_remote_settings()
    return str(settings.image_base_url or "").strip().rstrip("/")
