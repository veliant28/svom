from __future__ import annotations

from django.conf import settings as django_settings
from django.db import connections, router, transaction

from apps.autodb.models import AutoDbTranslationSettings


_AUTODB_TRANSLATION_SETTINGS_TABLE = AutoDbTranslationSettings._meta.db_table


def _translation_settings_db_alias() -> str:
    alias = router.db_for_read(AutoDbTranslationSettings)
    return str(alias or "default")


def has_autodb_translation_settings_table() -> bool:
    db_alias = _translation_settings_db_alias()
    connection = connections[db_alias]
    with connection.cursor() as cursor:
        table_names = connection.introspection.table_names(cursor)
    return _AUTODB_TRANSLATION_SETTINGS_TABLE in set(table_names)


@transaction.atomic
def get_autodb_translation_settings() -> AutoDbTranslationSettings:
    settings, created = AutoDbTranslationSettings.objects.get_or_create(
        code=AutoDbTranslationSettings.DEFAULT_CODE,
    )
    if created:
        provider = str(getattr(django_settings, "AUTODB_OFFLINE_TRANSLATE_PROVIDER", "libretranslate") or "libretranslate").strip().lower()
        if provider not in {AutoDbTranslationSettings.PROVIDER_GOOGLE, AutoDbTranslationSettings.PROVIDER_LIBRETRANSLATE}:
            provider = AutoDbTranslationSettings.PROVIDER_LIBRETRANSLATE
        settings.provider = provider
        settings.google_api_key = str(getattr(django_settings, "AUTODB_GOOGLE_TRANSLATE_API_KEY", "") or "").strip()
        settings.save(update_fields=("provider", "google_api_key", "updated_at"))
    return settings
