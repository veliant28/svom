from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from apps.seo.api.serializers import (
    GoogleEventSettingSerializer,
    GoogleIntegrationSettingsSerializer,
    SeoDashboardSerializer,
    SeoMetaOverrideSerializer,
    SeoMetaTemplateSerializer,
    SeoSiteSettingsSerializer,
)
from apps.seo.api.views._base import SeoBackofficeAPIView
from apps.seo.models import GoogleEventSetting, SeoMetaOverride, SeoMetaTemplate
from apps.seo.selectors import (
    get_google_integration_settings,
    get_seo_dashboard_payload,
    get_seo_site_settings,
    list_google_event_settings,
)
from apps.seo.services import rebuild_sitemap, render_robots_preview


class SeoBackofficeSettingsAPIView(SeoBackofficeAPIView):
    def get(self, request):
        serializer = SeoSiteSettingsSerializer(get_seo_site_settings())
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        settings = get_seo_site_settings()
        serializer = SeoSiteSettingsSerializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class SeoBackofficeGoogleSettingsAPIView(SeoBackofficeAPIView):
    def get(self, request):
        settings = get_google_integration_settings()
        settings_serializer = GoogleIntegrationSettingsSerializer(settings)
        events_serializer = GoogleEventSettingSerializer(list_google_event_settings(), many=True)
        return Response(
            {
                "settings": settings_serializer.data,
                "events": events_serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request):
        settings = get_google_integration_settings()
        serializer = GoogleIntegrationSettingsSerializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        events_payload = request.data.get("events")
        if isinstance(events_payload, list):
            updates_by_id: dict[str, bool] = {}
            updates_by_name: dict[str, bool] = {}
            for item in events_payload:
                if not isinstance(item, dict):
                    continue
                enabled = bool(item.get("is_enabled"))
                event_id = str(item.get("id") or "").strip()
                event_name = str(item.get("event_name") or "").strip()
                if event_id:
                    updates_by_id[event_id] = enabled
                elif event_name:
                    updates_by_name[event_name] = enabled

            if updates_by_id:
                for event in GoogleEventSetting.objects.filter(id__in=list(updates_by_id.keys())):
                    event.is_enabled = updates_by_id[str(event.id)]
                    event.save(update_fields=("is_enabled", "updated_at"))
            if updates_by_name:
                for event in GoogleEventSetting.objects.filter(event_name__in=list(updates_by_name.keys())):
                    event.is_enabled = updates_by_name[event.event_name]
                    event.save(update_fields=("is_enabled", "updated_at"))

        return self.get(request)


class SeoBackofficeTemplateListCreateAPIView(SeoBackofficeAPIView):
    def get(self, request):
        queryset = SeoMetaTemplate.objects.order_by("entity_type", "locale", "-updated_at")
        serializer = SeoMetaTemplateSerializer(queryset, many=True)
        return Response(
            {
                "count": len(serializer.data),
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = SeoMetaTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        output = SeoMetaTemplateSerializer(instance)
        return Response(output.data, status=status.HTTP_201_CREATED)


class SeoBackofficeTemplateRetrieveUpdateDestroyAPIView(SeoBackofficeAPIView):
    def patch(self, request, id):
        instance = get_object_or_404(SeoMetaTemplate, id=id)
        serializer = SeoMetaTemplateSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        output = SeoMetaTemplateSerializer(updated)
        return Response(output.data, status=status.HTTP_200_OK)

    def delete(self, request, id):
        instance = get_object_or_404(SeoMetaTemplate, id=id)
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SeoBackofficeOverrideListCreateAPIView(SeoBackofficeAPIView):
    def get(self, request):
        queryset = SeoMetaOverride.objects.order_by("path", "locale", "-updated_at")
        serializer = SeoMetaOverrideSerializer(queryset, many=True)
        return Response(
            {
                "count": len(serializer.data),
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = SeoMetaOverrideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        output = SeoMetaOverrideSerializer(instance)
        return Response(output.data, status=status.HTTP_201_CREATED)


class SeoBackofficeOverrideRetrieveUpdateDestroyAPIView(SeoBackofficeAPIView):
    def patch(self, request, id):
        instance = get_object_or_404(SeoMetaOverride, id=id)
        serializer = SeoMetaOverrideSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        output = SeoMetaOverrideSerializer(updated)
        return Response(output.data, status=status.HTTP_200_OK)

    def delete(self, request, id):
        instance = get_object_or_404(SeoMetaOverride, id=id)
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SeoBackofficeDashboardAPIView(SeoBackofficeAPIView):
    required_capability_read = "seo.view"
    required_capability_write = "seo.view"

    def get(self, request):
        serializer = SeoDashboardSerializer(get_seo_dashboard_payload())
        return Response(serializer.data, status=status.HTTP_200_OK)


class SeoBackofficeSitemapRebuildAPIView(SeoBackofficeAPIView):
    required_capability_read = "seo.manage"
    required_capability_write = "seo.manage"

    def post(self, request):
        payload = rebuild_sitemap()
        return Response(payload, status=status.HTTP_200_OK)


class SeoBackofficeRobotsPreviewAPIView(SeoBackofficeAPIView):
    def get(self, request):
        settings = get_seo_site_settings()
        return Response(
            {
                "robots_txt": render_robots_preview(settings),
            },
            status=status.HTTP_200_OK,
        )
