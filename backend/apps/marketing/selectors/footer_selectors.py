from __future__ import annotations

from apps.marketing.models import FooterSettings


def get_footer_settings() -> FooterSettings:
    settings, _ = FooterSettings.objects.get_or_create(code=FooterSettings.DEFAULT_CODE)
    return settings
