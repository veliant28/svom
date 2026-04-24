from .backoffice_views import (
    SeoBackofficeDashboardAPIView,
    SeoBackofficeGoogleSettingsAPIView,
    SeoBackofficeOverrideListCreateAPIView,
    SeoBackofficeOverrideRetrieveUpdateDestroyAPIView,
    SeoBackofficeRobotsPreviewAPIView,
    SeoBackofficeSettingsAPIView,
    SeoBackofficeSitemapRebuildAPIView,
    SeoBackofficeTemplateListCreateAPIView,
    SeoBackofficeTemplateRetrieveUpdateDestroyAPIView,
)
from .public_views import (
    SeoPublicConfigAPIView,
    SeoPublicGoogleConfigAPIView,
    SeoPublicResolveMetaAPIView,
    SeoPublicSiteConfigAPIView,
)

__all__ = [
    "SeoBackofficeSettingsAPIView",
    "SeoBackofficeGoogleSettingsAPIView",
    "SeoBackofficeTemplateListCreateAPIView",
    "SeoBackofficeTemplateRetrieveUpdateDestroyAPIView",
    "SeoBackofficeOverrideListCreateAPIView",
    "SeoBackofficeOverrideRetrieveUpdateDestroyAPIView",
    "SeoBackofficeDashboardAPIView",
    "SeoBackofficeSitemapRebuildAPIView",
    "SeoBackofficeRobotsPreviewAPIView",
    "SeoPublicConfigAPIView",
    "SeoPublicGoogleConfigAPIView",
    "SeoPublicSiteConfigAPIView",
    "SeoPublicResolveMetaAPIView",
]
