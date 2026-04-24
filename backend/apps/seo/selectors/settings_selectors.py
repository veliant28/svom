from __future__ import annotations

from django.db import transaction

from apps.seo.constants import DEFAULT_GOOGLE_EVENT_DEFINITIONS
from apps.seo.models import GoogleEventSetting, GoogleIntegrationSettings, SeoSiteSettings


def get_seo_site_settings() -> SeoSiteSettings:
    settings, _ = SeoSiteSettings.objects.get_or_create(code=SeoSiteSettings.DEFAULT_CODE)
    return settings


def get_google_integration_settings() -> GoogleIntegrationSettings:
    settings, _ = GoogleIntegrationSettings.objects.get_or_create(code=GoogleIntegrationSettings.DEFAULT_CODE)
    return settings


@transaction.atomic
def ensure_default_google_event_settings() -> None:
    for event_name, label, description in DEFAULT_GOOGLE_EVENT_DEFINITIONS:
        GoogleEventSetting.objects.get_or_create(
            event_name=event_name,
            defaults={
                "label": label,
                "description": description,
                "is_enabled": True,
            },
        )


def list_google_event_settings() -> list[GoogleEventSetting]:
    ensure_default_google_event_settings()
    return list(GoogleEventSetting.objects.order_by("event_name"))
