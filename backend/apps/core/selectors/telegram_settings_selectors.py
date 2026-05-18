from __future__ import annotations

from apps.core.models import TelegramSettings


def get_telegram_settings() -> TelegramSettings:
    settings, _ = TelegramSettings.objects.get_or_create(code=TelegramSettings.DEFAULT_CODE)
    return settings
