from __future__ import annotations

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.seo.api.serializers import (
    SeoPublicConfigSerializer,
    SeoPublicGoogleSettingsSerializer,
    SeoPublicSiteSettingsSerializer,
    SeoResolveMetaInputSerializer,
    SeoResolvedMetaSerializer,
)
from apps.seo.models import SeoMetaOverride, SeoMetaTemplate
from apps.seo.selectors import (
    get_google_integration_settings,
    get_seo_site_settings,
    list_google_event_settings,
)


class SeoPublicConfigAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        settings = get_seo_site_settings()
        google = get_google_integration_settings()
        events = list_google_event_settings()
        templates = SeoMetaTemplate.objects.filter(is_active=True).order_by("entity_type", "locale")
        overrides = SeoMetaOverride.objects.filter(is_active=True).order_by("path", "locale")

        serializer = SeoPublicConfigSerializer(
            {
                "settings": settings,
                "google": google,
                "events": list(events),
                "templates": list(templates),
                "overrides": list(overrides),
            }
        )
        return Response(serializer.data)


class SeoPublicGoogleConfigAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        serializer = SeoPublicGoogleSettingsSerializer(get_google_integration_settings())
        return Response(serializer.data)


class SeoPublicSiteConfigAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        serializer = SeoPublicSiteSettingsSerializer(get_seo_site_settings())
        return Response(serializer.data)


class SeoPublicResolveMetaAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        serializer = SeoResolveMetaInputSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        output = SeoResolvedMetaSerializer(serializer.to_resolved_payload())
        return Response(output.data)
