from __future__ import annotations

import re

from rest_framework import serializers

from apps.seo.constants import SEO_ALLOWED_TEMPLATE_PLACEHOLDERS
from apps.seo.models import SeoMetaTemplate


PLACEHOLDER_PATTERN = re.compile(r"\{[^{}]+\}")


def validate_template_placeholders(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    placeholders = set(PLACEHOLDER_PATTERN.findall(normalized))
    invalid = sorted(item for item in placeholders if item not in SEO_ALLOWED_TEMPLATE_PLACEHOLDERS)
    if invalid:
        raise serializers.ValidationError(
            {
                "code": "SEO_INVALID_TEMPLATE_PLACEHOLDERS",
                "allowed": list(SEO_ALLOWED_TEMPLATE_PLACEHOLDERS),
                "invalid": invalid,
            }
        )
    return normalized


class SeoMetaTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SeoMetaTemplate
        fields = (
            "id",
            "entity_type",
            "locale",
            "title_template",
            "description_template",
            "h1_template",
            "og_title_template",
            "og_description_template",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_title_template(self, value: str) -> str:
        return validate_template_placeholders(value)

    def validate_description_template(self, value: str) -> str:
        return validate_template_placeholders(value)

    def validate_h1_template(self, value: str) -> str:
        return validate_template_placeholders(value)

    def validate_og_title_template(self, value: str) -> str:
        return validate_template_placeholders(value)

    def validate_og_description_template(self, value: str) -> str:
        return validate_template_placeholders(value)
