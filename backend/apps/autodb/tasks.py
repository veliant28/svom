from __future__ import annotations

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.autodb.models import AutoDbSupplier
from apps.autodb.services.article_enrichment import AutoDbArticleEnrichmentService
from apps.autodb.services.product_attribute_enrichment import AutoDbProductAttributeEnrichmentService
from apps.autodb.services.product_fitment_enrichment import AutoDbProductFitmentEnrichmentService
from apps.autodb.services.product_image_enrichment import AutoDbProductImageEnrichmentService
from apps.autodb.services.product_name_enrichment import AutoDbProductNameEnrichmentService
from apps.autodb.services.product_name_translation import ProductNameTranslationService
from apps.catalog.models import AutoDbArticleManualMapping, AutoDbProductLinkQuality, Product
from apps.catalog.services import resolve_autodb_article_name
from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand


@shared_task(name="autodb.manual_bind_product")
def manual_bind_product_to_autodb_task(
    *,
    product_id: str,
    supplier_id: int,
    article_number: str,
    supplier_name: str = "",
    article_id: int | None = None,
    actor_id: str = "",
) -> dict[str, object]:
    article_value = str(article_number or "").strip().upper()
    if not product_id or not supplier_id or not article_value:
        return {
            "status": "validation_error",
            "detail": "product_id, supplier_id, article_number are required",
        }

    supplier = AutoDbSupplier.objects.filter(id=int(supplier_id)).first()
    supplier_display = str(supplier_name or "").strip() or str(getattr(supplier, "name", "") or "").strip() or str(
        getattr(supplier, "matchcode", "") or ""
    ).strip()
    if not supplier_display:
        supplier_display = str(int(supplier_id))

    article_key = f"{int(supplier_id)}:{article_value}"
    now = timezone.now()
    normalized_article = normalize_article(article_value)
    normalized_supplier = normalize_brand(supplier_display)

    with transaction.atomic():
        product = Product.objects.select_related("brand").filter(pk=product_id).first()
        if product is None:
            return {"status": "not_found", "detail": "product not found", "product_id": str(product_id)}

        update_fields: list[str] = []

        if int(getattr(product, "autodb_supplier_id", 0) or 0) != int(supplier_id):
            product.autodb_supplier_id = int(supplier_id)
            update_fields.append("autodb_supplier_id")
        if str(getattr(product, "autodb_supplier_name", "") or "") != supplier_display:
            product.autodb_supplier_name = supplier_display
            update_fields.append("autodb_supplier_name")
        if str(getattr(product, "autodb_article_number", "") or "") != article_value:
            product.autodb_article_number = article_value
            update_fields.append("autodb_article_number")
        if str(getattr(product, "autodb_article_key", "") or "") != article_key:
            product.autodb_article_key = article_key
            update_fields.append("autodb_article_key")

        if article_id is not None:
            try:
                parsed_article_id = int(article_id)
            except (TypeError, ValueError):
                parsed_article_id = None
            if parsed_article_id and int(getattr(product, "autodb_article_id", 0) or 0) != parsed_article_id:
                product.autodb_article_id = parsed_article_id
                update_fields.append("autodb_article_id")

        if normalized_article and str(getattr(product, "normalized_article", "") or "") != normalized_article:
            product.normalized_article = normalized_article
            update_fields.append("normalized_article")
        if normalized_supplier and str(getattr(product, "normalized_brand", "") or "") != normalized_supplier:
            product.normalized_brand = normalized_supplier
            update_fields.append("normalized_brand")

        if not bool(getattr(product, "brand_manually_locked", False)):
            if str(getattr(product, "display_brand_name", "") or "") != supplier_display:
                product.display_brand_name = supplier_display
                update_fields.append("display_brand_name")
            if str(getattr(product, "brand_source", "") or "") != Product.BRAND_SOURCE_AUTODB_PRO:
                product.brand_source = Product.BRAND_SOURCE_AUTODB_PRO
                update_fields.append("brand_source")

        if str(getattr(product, "catalog_source", "") or "") != Product.CATALOG_SOURCE_AUTODB_PRO:
            product.catalog_source = Product.CATALOG_SOURCE_AUTODB_PRO
            update_fields.append("catalog_source")

        if not bool(getattr(product, "name_manually_locked", False)):
            previous_name = str(getattr(product, "name", "") or "")
            previous_source_text = str(getattr(product, "name_source_text", "") or "")
            article_name = resolve_autodb_article_name(
                normalized_article=normalized_article,
                normalized_brand=normalized_supplier,
                prefer_live=True,
            )
            normalized_article_name = str(article_name or "").strip()[:255]
            if normalized_article_name:
                article_name = normalized_article_name
            translation_source_text = str(article_name or previous_source_text or previous_name).strip()[:255]
            if article_name and str(getattr(product, "name_source", "") or "") != Product.NAME_SOURCE_AUTODB_PRO:
                product.name_source = Product.NAME_SOURCE_AUTODB_PRO
                update_fields.append("name_source")
            if article_name and str(getattr(product, "name_source_text", "") or "") != article_name:
                product.name_source_text = article_name
                update_fields.append("name_source_text")
            if translation_source_text:
                translation = ProductNameTranslationService().translate_product_name(source_text=translation_source_text)
                translated_uk = str(translation.uk or article_name).strip()[:255]
                translated_ru = str(translation.ru or article_name).strip()[:255]
                translated_en = str(translation.en or article_name).strip()[:255]

                i18n_targets = {
                    "name_uk": translated_uk,
                    "name_ru": translated_ru,
                    "name_en": translated_en,
                }
                for field, next_value in i18n_targets.items():
                    current_value = str(getattr(product, field, "") or "")
                    if (
                        not current_value
                        or current_value == previous_name
                        or current_value == previous_source_text
                        or str(getattr(product, "name_source", "") or "") == Product.NAME_SOURCE_AUTODB_PRO
                    ):
                        if current_value != next_value:
                            setattr(product, field, next_value)
                            update_fields.append(field)

                base_name = translated_uk or translation_source_text
                if base_name and str(getattr(product, "name", "") or "") != base_name:
                    product.name = base_name
                    update_fields.append("name")

                translation_status = str(translation.status or "").strip() or Product.NAME_TRANSLATION_PENDING
                if str(getattr(product, "name_translation_status", "") or "") != translation_status:
                    product.name_translation_status = translation_status
                    update_fields.append("name_translation_status")
                translation_error = str(translation.error or "").strip()
                if str(getattr(product, "name_translation_error", "") or "") != translation_error:
                    product.name_translation_error = translation_error
                    update_fields.append("name_translation_error")

        if update_fields:
            product.save(update_fields=[*update_fields, "updated_at"])

        manual_mapping_defaults = {
            "brand": supplier_display,
            "article": article_value,
            "autodb_supplier_id": int(supplier_id),
            "autodb_article_number": article_value,
            "autodb_article_key": article_key,
            "manual_confirmed": True,
            "source": "backoffice_manual_search_bind",
            "note": f"actor={actor_id}" if actor_id else "backoffice_manual_search_bind",
        }
        if article_id is not None:
            try:
                parsed_article_id = int(article_id)
            except (TypeError, ValueError):
                parsed_article_id = None
            if parsed_article_id:
                manual_mapping_defaults["autodb_article_id"] = parsed_article_id

        AutoDbArticleManualMapping.objects.update_or_create(
            normalized_brand=normalized_supplier or normalize_brand(getattr(product.brand, "name", "")),
            normalized_article=normalized_article,
            autodb_article_key=article_key,
            defaults=manual_mapping_defaults,
        )

        quality_defaults = {
            "autodb_supplier_id": int(supplier_id),
            "autodb_article_number": article_value,
            "status": AutoDbProductLinkQuality.STATUS_TRUSTED,
            "reason": "manual_bind_from_backoffice",
            "evidence": {
                "source": "backoffice.autodb-matching.manual-search",
                "actor_id": actor_id,
                "supplier_id": int(supplier_id),
                "supplier_name": supplier_display,
                "article_number": article_value,
            },
            "checked_at": now,
            "manually_confirmed": True,
            "note": "manual bind",
        }
        quality, created = AutoDbProductLinkQuality.objects.get_or_create(
            product=product,
            autodb_article_key=article_key,
            defaults=quality_defaults,
        )
        if not created:
            quality.autodb_supplier_id = int(supplier_id)
            quality.autodb_article_number = article_value
            quality.status = AutoDbProductLinkQuality.STATUS_TRUSTED
            quality.reason = "manual_bind_from_backoffice"
            quality.evidence = quality_defaults["evidence"]
            quality.checked_at = now
            quality.manually_confirmed = True
            quality.note = "manual bind"
            quality.save(
                update_fields=[
                    "autodb_supplier_id",
                    "autodb_article_number",
                    "status",
                    "reason",
                    "evidence",
                    "checked_at",
                    "manually_confirmed",
                    "note",
                    "updated_at",
                ]
            )

        clone_result = AutoDbArticleEnrichmentService().enrich_article(
            supplier_id=int(supplier_id),
            article_number=article_value,
            dry_run=False,
        )
        name_result = AutoDbProductNameEnrichmentService().enrich_product(
            product=product,
            dry_run=False,
            only_missing_translations=False,
        )
        fitment_result = AutoDbProductFitmentEnrichmentService().enrich_product(product=product, dry_run=False)
        attribute_result = AutoDbProductAttributeEnrichmentService().enrich_product(product=product, dry_run=False)
        image_result = AutoDbProductImageEnrichmentService().sync_product_images(product=product, dry_run=False)

    return {
        "status": "bound",
        "product_id": str(product_id),
        "autodb_article_key": article_key,
        "quality_created": bool(created),
        "clone": {
            "remote_queries": int(clone_result.remote_queries),
            "remote_hits": int(clone_result.remote_hits),
            "populated_tables": clone_result.populated_tables,
        },
        "name": {
            "status": name_result.status,
            "source_title": name_result.autodb_source_title,
            "name_uk": name_result.new_name_uk,
            "name_ru": name_result.new_name_ru,
            "name_en": name_result.new_name_en,
            "translation_status": name_result.translation_status,
            "translation_error": name_result.translation_error,
        },
        "fitments": {
            "status": fitment_result.status,
            "created": int(fitment_result.fitments_created),
            "updated": int(fitment_result.fitments_updated),
            "stale_marked": int(fitment_result.stale_marked),
        },
        "attributes": {
            "status": attribute_result.status,
            "created": int(attribute_result.product_attributes_created),
            "updated": int(attribute_result.product_attributes_updated),
        },
        "images": {
            "created": int(image_result.created),
            "reused": int(image_result.reused),
            "stale_marked": int(image_result.stale_marked),
        },
    }
