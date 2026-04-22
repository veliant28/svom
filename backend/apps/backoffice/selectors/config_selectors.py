from __future__ import annotations

from django.db.models import QuerySet

from apps.supplier_imports.models import ArticleNormalizationRule, ImportSource, SupplierBrandAlias


def get_import_schedule_sources_queryset() -> QuerySet[ImportSource]:
    return ImportSource.objects.select_related("supplier", "integration").order_by("name")


def get_supplier_brand_aliases_queryset() -> QuerySet[SupplierBrandAlias]:
    return SupplierBrandAlias.objects.select_related("source", "supplier", "canonical_brand").order_by(
        "supplier__code",
        "source__code",
        "-priority",
        "supplier_brand_alias",
    )


def get_article_normalization_rules_queryset() -> QuerySet[ArticleNormalizationRule]:
    return ArticleNormalizationRule.objects.select_related("source").order_by("-priority", "name")
