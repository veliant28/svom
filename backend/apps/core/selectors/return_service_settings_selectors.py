from __future__ import annotations

from apps.core.models import ReturnServiceSettings


def get_return_service_settings() -> ReturnServiceSettings:
    settings, _ = ReturnServiceSettings.objects.get_or_create(code=ReturnServiceSettings.DEFAULT_CODE)
    return settings
