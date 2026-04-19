from __future__ import annotations

from django.db import transaction

from apps.autocatalog.models import UtrArticleDetailMap


@transaction.atomic
def upsert_mapping(
    *,
    article: str,
    normalized_article: str,
    brand_name: str,
    normalized_brand: str,
    utr_detail_id: str,
) -> bool:
    mapping = UtrArticleDetailMap.objects.filter(
        normalized_article=normalized_article,
        normalized_brand=normalized_brand,
    ).first()
    if mapping is None:
        UtrArticleDetailMap.objects.create(
            article=article,
            normalized_article=normalized_article,
            brand_name=brand_name,
            normalized_brand=normalized_brand,
            utr_detail_id=utr_detail_id,
        )
        return True

    changed = False
    if mapping.article != article:
        mapping.article = article
        changed = True
    if mapping.brand_name != brand_name:
        mapping.brand_name = brand_name
        changed = True
    if mapping.utr_detail_id != utr_detail_id:
        mapping.utr_detail_id = utr_detail_id
        changed = True
    if changed:
        mapping.save(update_fields=("article", "brand_name", "utr_detail_id", "updated_at"))
    return False


def track_unresolved(*, pair: dict[str, str], summary, upsert_func=upsert_mapping) -> None:
    unresolved_created = upsert_func(
        article=pair["article"],
        normalized_article=pair["normalized_article"],
        brand_name=pair["brand_name"],
        normalized_brand=pair["normalized_brand"],
        utr_detail_id="",
    )
    if unresolved_created:
        summary.unresolved_created += 1
    else:
        summary.unresolved_updated += 1
