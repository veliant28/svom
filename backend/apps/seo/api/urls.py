from django.urls import path

from apps.seo.api.views import (
    SeoBackofficeDashboardAPIView,
    SeoBackofficeGoogleSettingsAPIView,
    SeoBackofficeOverrideListCreateAPIView,
    SeoBackofficeOverrideRetrieveUpdateDestroyAPIView,
    SeoBackofficeRobotsPreviewAPIView,
    SeoBackofficeSettingsAPIView,
    SeoBackofficeSitemapRebuildAPIView,
    SeoBackofficeTemplateListCreateAPIView,
    SeoBackofficeTemplateRetrieveUpdateDestroyAPIView,
    SeoPublicConfigAPIView,
    SeoPublicGoogleConfigAPIView,
    SeoPublicResolveMetaAPIView,
    SeoPublicSiteConfigAPIView,
)

app_name = "seo_api"

urlpatterns = [
    path("backoffice/settings/", SeoBackofficeSettingsAPIView.as_view(), name="backoffice-settings"),
    path("backoffice/google/", SeoBackofficeGoogleSettingsAPIView.as_view(), name="backoffice-google"),
    path("backoffice/templates/", SeoBackofficeTemplateListCreateAPIView.as_view(), name="backoffice-template-list"),
    path(
        "backoffice/templates/<uuid:id>/",
        SeoBackofficeTemplateRetrieveUpdateDestroyAPIView.as_view(),
        name="backoffice-template-detail",
    ),
    path("backoffice/overrides/", SeoBackofficeOverrideListCreateAPIView.as_view(), name="backoffice-override-list"),
    path(
        "backoffice/overrides/<uuid:id>/",
        SeoBackofficeOverrideRetrieveUpdateDestroyAPIView.as_view(),
        name="backoffice-override-detail",
    ),
    path("backoffice/dashboard/", SeoBackofficeDashboardAPIView.as_view(), name="backoffice-dashboard"),
    path("backoffice/sitemap/rebuild/", SeoBackofficeSitemapRebuildAPIView.as_view(), name="backoffice-sitemap-rebuild"),
    path("backoffice/robots/preview/", SeoBackofficeRobotsPreviewAPIView.as_view(), name="backoffice-robots-preview"),
    path("public/config/", SeoPublicConfigAPIView.as_view(), name="public-config"),
    path("public/google/", SeoPublicGoogleConfigAPIView.as_view(), name="public-google"),
    path("public/site/", SeoPublicSiteConfigAPIView.as_view(), name="public-site"),
    path("public/resolve-meta/", SeoPublicResolveMetaAPIView.as_view(), name="public-resolve-meta"),
]
