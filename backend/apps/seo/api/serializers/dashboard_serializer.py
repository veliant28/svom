from __future__ import annotations

from rest_framework import serializers


class SeoHealthItemSerializer(serializers.Serializer):
    entity = serializers.CharField()
    label = serializers.CharField()
    total = serializers.IntegerField()
    missing_title = serializers.IntegerField()
    missing_description = serializers.IntegerField()
    ok = serializers.IntegerField()


class MissingMetaItemSerializer(serializers.Serializer):
    entity = serializers.CharField()
    missing_title = serializers.IntegerField()
    missing_description = serializers.IntegerField()


class GoogleEventStateSerializer(serializers.Serializer):
    event_name = serializers.CharField()
    label = serializers.CharField()
    enabled = serializers.BooleanField()


class TemplateEntityCountSerializer(serializers.Serializer):
    entity_type = serializers.CharField()
    total = serializers.IntegerField()


class SeoDashboardSerializer(serializers.Serializer):
    products_count = serializers.IntegerField()
    categories_count = serializers.IntegerField()
    brands_count = serializers.IntegerField()
    active_overrides_count = serializers.IntegerField()
    active_templates_count = serializers.IntegerField()

    sitemap_enabled = serializers.BooleanField()
    google_enabled = serializers.BooleanField()
    ga4_configured = serializers.BooleanField()
    gtm_configured = serializers.BooleanField()
    search_console_configured = serializers.BooleanField()

    missing_meta_available = serializers.BooleanField()
    seo_health_by_entity = SeoHealthItemSerializer(many=True)
    missing_meta_by_type = MissingMetaItemSerializer(many=True)
    google_events_state = GoogleEventStateSerializer(many=True)
    templates_by_entity = TemplateEntityCountSerializer(many=True)
