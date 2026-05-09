from __future__ import annotations

from django.db import transaction

from apps.autodb.models import AutoDbArticleProductGroup, AutoDbProductGroup, AutoDbSupplier
from apps.catalog.models import AutoDbPrdCategoryMap, Category
from apps.catalog.services.category_assignment import assignable_category_or_none
from apps.catalog.services.category_management import find_category_by_normalized_name
from apps.catalog.services.taxonomy_v2 import find_seeded_leaf_by_name
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand


def resolve_autodb_category_for_raw_offer(*, raw_offer: SupplierRawOffer) -> Category | None:
    article = normalize_article(raw_offer.normalized_article or raw_offer.article or raw_offer.external_sku)
    brand = normalize_brand(raw_offer.normalized_brand or raw_offer.brand_name)
    if not article or not brand:
        return None

    supplier_ids = set(
        AutoDbSupplier.objects.filter(normalized_matchcode=brand).values_list("id", flat=True)
    )
    supplier_ids.update(
        AutoDbSupplier.objects.filter(normalized_name=brand).values_list("id", flat=True)
    )
    if not supplier_ids:
        return None

    group_ids = list(
        AutoDbArticleProductGroup.objects.filter(
            supplier_id__in=sorted(int(value) for value in supplier_ids),
            normalized_article=article,
        )
        .values_list("product_group_id", flat=True)
        .distinct()
    )
    if not group_ids:
        return None

    mapped = AutoDbPrdCategoryMap.objects.filter(prd_id__in=group_ids).select_related("category").order_by("updated_at").first()
    if mapped is not None:
        return assignable_category_or_none(mapped.category)

    groups = AutoDbProductGroup.objects.filter(id__in=group_ids).order_by("id")
    for group in groups:
        group_name = str(group.name or "").strip()
        if not group_name:
            continue
        category = find_seeded_leaf_by_name(group_name) or find_category_by_normalized_name(name=group_name, parent=None)
        category = assignable_category_or_none(category)
        if category is None:
            continue
        with transaction.atomic():
            AutoDbPrdCategoryMap.objects.get_or_create(
                prd_id=int(group.id),
                defaults={
                    "prd_name": group_name[:255],
                    "category": category,
                    "source": AutoDbPrdCategoryMap.SOURCE_AUTO,
                    "confidence": None,
                },
            )
        return category

    return None
