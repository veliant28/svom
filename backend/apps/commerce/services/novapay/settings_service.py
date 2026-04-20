from __future__ import annotations

from apps.commerce.models import NovaPaySettings


def get_novapay_settings() -> NovaPaySettings:
    settings, _ = NovaPaySettings.objects.get_or_create(code=NovaPaySettings.DEFAULT_CODE)
    return settings
