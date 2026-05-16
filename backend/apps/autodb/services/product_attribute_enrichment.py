from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
import json
from typing import Any

from django.db.models import F, QuerySet
from django.utils.text import slugify

from apps.autodb.services.column_helpers import find_column_name, find_value
from apps.autodb.services.product_name_translation import ProductNameTranslationService
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.catalog.models import Attribute, AttributeValue, AutoDbProductLinkQuality, Product, ProductAttribute
from apps.catalog.services import sanitize_product_name


@dataclass(frozen=True)
class ProductAttributeProposal:
    attribute_name: str
    attribute_value: str
    autodb_attribute_id: int | None
    source_row: dict[str, Any]


@dataclass(frozen=True)
class ProductAttributeEnrichmentResult:
    product_id: str
    status: str
    attributes_found: int
    attributes_created: int
    attributes_reused: int
    values_created: int
    product_attributes_created: int
    product_attributes_updated: int
    skipped_manual_locked: int
    translation_pending: int
    warning: str = ""
    error: str = ""


@dataclass(frozen=True)
class ProductAttributeDiagnostics:
    product_id: str
    bridge_supplier_id: int | None
    bridge_article_number: str
    bridge_article_key: str
    raw_rows: tuple[dict[str, Any], ...]
    proposals: tuple[dict[str, Any], ...]
    current_attributes: tuple[dict[str, Any], ...]
    skipped_reason: str


class AutoDbProductAttributeEnrichmentService:
    def __init__(
        self,
        *,
        storage: AutoDbRawCloneStorage | None = None,
        translator: ProductNameTranslationService | None = None,
    ):
        self.storage = storage or AutoDbRawCloneStorage()
        self.translator = translator or ProductNameTranslationService()
        self._dry_run_attribute_cache: dict[str, Attribute] = {}
        self._dry_run_value_cache: dict[tuple[str, str], AttributeValue] = {}

    def build_queryset(
        self,
        *,
        only_linked: bool,
        only_trusted: bool,
        only_missing: bool,
        product_id: str,
    ) -> QuerySet[Product]:
        qs = Product.objects.select_related("category").prefetch_related(
            "product_attributes",
            "product_attributes__attribute",
            "product_attributes__attribute_value",
        ).order_by("id")
        if only_linked:
            qs = qs.filter(autodb_supplier_id__isnull=False).exclude(autodb_article_number="")
        if only_trusted:
            qs = qs.filter(
                autodb_link_qualities__status=AutoDbProductLinkQuality.STATUS_TRUSTED,
                autodb_link_qualities__autodb_article_key=F("autodb_article_key"),
            )
        if only_missing:
            qs = qs.filter(product_attributes__isnull=True)
        if product_id:
            qs = qs.filter(pk=product_id)
        return qs.distinct()

    def enrich_product(self, *, product: Product, dry_run: bool) -> ProductAttributeEnrichmentResult:
        supplier_id = self._safe_int(getattr(product, "autodb_supplier_id", None))
        article_number = str(getattr(product, "autodb_article_number", "") or "").strip()
        if supplier_id is None or not article_number:
            return ProductAttributeEnrichmentResult(
                product_id=str(product.id),
                status="skipped_no_autodb_link",
                attributes_found=0,
                attributes_created=0,
                attributes_reused=0,
                values_created=0,
                product_attributes_created=0,
                product_attributes_updated=0,
                skipped_manual_locked=0,
                translation_pending=0,
            )

        rows = self._find_article_attribute_rows(supplier_id=supplier_id, article_number=article_number)
        proposals = self._build_proposals(rows)
        if not proposals:
            return ProductAttributeEnrichmentResult(
                product_id=str(product.id),
                status="skipped_no_article_attributes",
                attributes_found=0,
                attributes_created=0,
                attributes_reused=0,
                values_created=0,
                product_attributes_created=0,
                product_attributes_updated=0,
                skipped_manual_locked=0,
                translation_pending=0,
            )

        by_attribute_id: dict[str, ProductAttribute] = {}
        for item in product.product_attributes.select_related("attribute", "attribute_value").all():
            by_attribute_id[str(item.attribute_id)] = item

        attributes_created = 0
        attributes_reused = 0
        values_created = 0
        product_attributes_created = 0
        product_attributes_updated = 0
        skipped_manual_locked = 0
        translation_pending = 0

        for proposal in proposals:
            attribute, attr_created, attr_reused, attr_translation_pending = self._ensure_attribute(
                name=proposal.attribute_name,
                autodb_attribute_id=proposal.autodb_attribute_id,
                dry_run=dry_run,
            )
            if attribute is None:
                continue
            if attr_created:
                attributes_created += 1
            if attr_reused:
                attributes_reused += 1
            if attr_translation_pending:
                translation_pending += 1

            existing = by_attribute_id.get(str(attribute.id))
            if existing is not None and (
                bool(existing.manual_locked) or str(existing.source or "") == ProductAttribute.SOURCE_MANUAL
            ):
                skipped_manual_locked += 1
                continue

            value, value_created = self._ensure_value(
                attribute=attribute,
                value=proposal.attribute_value,
                autodb_attribute_id=proposal.autodb_attribute_id,
                dry_run=dry_run,
            )
            if value is None:
                continue
            if value_created:
                values_created += 1

            source_payload = {
                "source": "autodb_pro",
                "supplier_id": supplier_id,
                "article_number": article_number,
                "attribute": {
                    "id": proposal.autodb_attribute_id,
                    "name": proposal.attribute_name,
                    "value": proposal.attribute_value,
                },
            }
            source_hash = sha1(json.dumps(source_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()  # noqa: S324

            if existing is None:
                item = ProductAttribute(
                    product=product,
                    attribute=attribute,
                    attribute_value=value,
                    raw_value=proposal.attribute_value,
                    source=ProductAttribute.SOURCE_AUTODB_PRO,
                    source_payload=source_payload,
                    source_hash=source_hash,
                    autodb_attribute_id=proposal.autodb_attribute_id,
                    manual_locked=False,
                )
                if not dry_run:
                    item.save()
                    by_attribute_id[str(attribute.id)] = item
                product_attributes_created += 1
                continue

            changed = False
            if existing.attribute_value_id != value.id:
                existing.attribute_value = value
                changed = True
            if str(existing.raw_value or "") != proposal.attribute_value:
                existing.raw_value = proposal.attribute_value
                changed = True
            if str(existing.source or "") != ProductAttribute.SOURCE_AUTODB_PRO:
                existing.source = ProductAttribute.SOURCE_AUTODB_PRO
                changed = True
            if existing.source_payload != source_payload:
                existing.source_payload = source_payload
                changed = True
            if str(existing.source_hash or "") != source_hash:
                existing.source_hash = source_hash
                changed = True
            if proposal.autodb_attribute_id is not None and existing.autodb_attribute_id != proposal.autodb_attribute_id:
                existing.autodb_attribute_id = proposal.autodb_attribute_id
                changed = True

            if changed:
                product_attributes_updated += 1
                if not dry_run:
                    existing.save(
                        update_fields=(
                            "attribute_value",
                            "raw_value",
                            "source",
                            "source_payload",
                            "source_hash",
                            "autodb_attribute_id",
                            "updated_at",
                        )
                    )

        if product_attributes_created or product_attributes_updated:
            status = "updated"
        elif skipped_manual_locked and not (attributes_created or values_created):
            status = "skipped_manual_locked"
        else:
            status = "skipped_hash_unchanged"

        return ProductAttributeEnrichmentResult(
            product_id=str(product.id),
            status=status,
            attributes_found=len(proposals),
            attributes_created=attributes_created,
            attributes_reused=attributes_reused,
            values_created=values_created,
            product_attributes_created=product_attributes_created,
            product_attributes_updated=product_attributes_updated,
            skipped_manual_locked=skipped_manual_locked,
            translation_pending=translation_pending,
        )

    def build_diagnostics(self, *, product: Product) -> ProductAttributeDiagnostics:
        supplier_id = self._safe_int(getattr(product, "autodb_supplier_id", None))
        article_number = str(getattr(product, "autodb_article_number", "") or "").strip()
        if supplier_id is None or not article_number:
            return ProductAttributeDiagnostics(
                product_id=str(product.id),
                bridge_supplier_id=supplier_id,
                bridge_article_number=article_number,
                bridge_article_key=str(getattr(product, "autodb_article_key", "") or ""),
                raw_rows=(),
                proposals=(),
                current_attributes=self._serialize_current_attributes(product),
                skipped_reason="skipped_no_autodb_link",
            )

        rows = self._find_article_attribute_rows(supplier_id=supplier_id, article_number=article_number)
        proposals = self._build_proposals(rows)
        skipped_reason = ""
        if not proposals:
            skipped_reason = "skipped_no_article_attributes"

        return ProductAttributeDiagnostics(
            product_id=str(product.id),
            bridge_supplier_id=supplier_id,
            bridge_article_number=article_number,
            bridge_article_key=str(getattr(product, "autodb_article_key", "") or ""),
            raw_rows=tuple(dict(row) for row in rows),
            proposals=tuple(
                {
                    "attribute_name": item.attribute_name,
                    "attribute_value": item.attribute_value,
                    "autodb_attribute_id": item.autodb_attribute_id,
                }
                for item in proposals
            ),
            current_attributes=self._serialize_current_attributes(product),
            skipped_reason=skipped_reason,
        )

    def _serialize_current_attributes(self, product: Product) -> tuple[dict[str, Any], ...]:
        rows: list[dict[str, Any]] = []
        for item in product.product_attributes.select_related("attribute", "attribute_value").all():
            rows.append(
                {
                    "product_attribute_id": str(item.id),
                    "attribute_name": str(getattr(item.attribute, "name", "") or ""),
                    "value": str(getattr(getattr(item, "attribute_value", None), "value", "") or item.raw_value or ""),
                    "source": str(item.source or ""),
                    "manual_locked": bool(item.manual_locked),
                    "autodb_attribute_id": self._safe_int(item.autodb_attribute_id),
                }
            )
        return tuple(rows)

    def _build_proposals(self, rows: list[dict[str, Any]]) -> list[ProductAttributeProposal]:
        def _row_sort_key(item: dict[str, Any]) -> tuple[int, str, str]:
            raw_id = self._safe_int(find_value(item, ["id", "ID"]))
            return (raw_id if raw_id is not None else 10**12, str(item.get("displaytitle") or item.get("description") or ""), str(item.get("displayvalue") or ""))

        proposals: list[ProductAttributeProposal] = []
        dedupe_names: set[str] = set()
        for row in sorted(rows, key=_row_sort_key):
            name = self._extract_attribute_name(row)
            value = self._extract_attribute_value(row)
            if not name or not value:
                continue
            name_key = name.lower()
            if name_key in dedupe_names:
                continue
            dedupe_names.add(name_key)
            proposals.append(
                ProductAttributeProposal(
                    attribute_name=name,
                    attribute_value=value,
                    autodb_attribute_id=self._safe_int(find_value(row, ["id", "ID"])),
                    source_row=dict(row),
                )
            )
        return proposals

    def _extract_attribute_name(self, row: dict[str, Any]) -> str:
        for key in ["displaytitle", "DisplayTitle", "description", "Description"]:
            value = sanitize_product_name(str(find_value(row, [key]) or ""))
            if value:
                return value[:120]
        return ""

    def _extract_attribute_value(self, row: dict[str, Any]) -> str:
        for key in ["displayvalue", "DisplayValue", "value", "Value"]:
            value = sanitize_product_name(str(find_value(row, [key]) or ""))
            if value:
                return value[:255]
        return ""

    def _ensure_attribute(
        self,
        *,
        name: str,
        autodb_attribute_id: int | None,
        dry_run: bool,
    ) -> tuple[Attribute | None, bool, bool, bool]:
        clean_name = sanitize_product_name(name)
        if not clean_name:
            return None, False, False, False

        translation = self.translator.translate_product_name(source_text=clean_name)
        name_uk = translation.uk or clean_name
        name_ru = translation.ru or clean_name
        name_en = translation.en or clean_name
        canonical_name = name_ru or clean_name
        translation_pending = translation.status != Product.NAME_TRANSLATION_TRANSLATED

        source_payload = {
            "source": "autodb_pro",
            "translation_status": "pending" if translation_pending else "translated",
            "name_source": clean_name,
            "autodb_attribute_id": autodb_attribute_id,
        }
        source_hash = sha1(json.dumps(source_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()  # noqa: S324

        cache_key = f"{autodb_attribute_id}:{canonical_name.lower()}"
        attribute = self._dry_run_attribute_cache.get(cache_key) if dry_run else None
        if attribute is None and autodb_attribute_id is not None:
            attribute = Attribute.objects.filter(autodb_attribute_id=autodb_attribute_id).order_by("id").first()
        if attribute is None:
            attribute = Attribute.objects.filter(name=canonical_name).order_by("id").first()
        if attribute is None:
            attribute = Attribute.objects.filter(name__iexact=canonical_name).order_by("id").first()

        created = False
        reused = attribute is not None
        if attribute is None:
            slug = self._generate_unique_slug(canonical_name)
            attribute = Attribute(
                name=canonical_name,
                name_uk=name_uk,
                name_ru=name_ru,
                name_en=name_en,
                slug=slug,
                value_type=Attribute.TYPE_SELECT,
                is_filterable=True,
                autodb_attribute_id=autodb_attribute_id,
                source=Attribute.SOURCE_AUTODB_PRO,
                source_payload=source_payload,
                source_hash=source_hash,
            )
            created = True
            reused = False
            if not dry_run:
                attribute.save()
            else:
                self._dry_run_attribute_cache[cache_key] = attribute

        if attribute is None:
            return None, created, reused, translation_pending

        if not created and not dry_run:
            updates: list[str] = []
            if str(attribute.source or "") != Attribute.SOURCE_MANUAL:
                if sanitize_product_name(str(attribute.name or "")) != canonical_name and canonical_name:
                    attribute.name = canonical_name
                    updates.append("name")
                if sanitize_product_name(str(attribute.name_uk or attribute.name)) != name_uk and name_uk:
                    attribute.name_uk = name_uk
                    updates.append("name_uk")
                if str(attribute.name_ru or "") != name_ru and name_ru:
                    attribute.name_ru = name_ru
                    updates.append("name_ru")
                if str(attribute.name_en or "") != name_en and name_en:
                    attribute.name_en = name_en
                    updates.append("name_en")
                if str(attribute.source or "") != Attribute.SOURCE_AUTODB_PRO:
                    attribute.source = Attribute.SOURCE_AUTODB_PRO
                    updates.append("source")
                if attribute.source_payload != source_payload:
                    attribute.source_payload = source_payload
                    updates.append("source_payload")
                if str(attribute.source_hash or "") != source_hash:
                    attribute.source_hash = source_hash
                    updates.append("source_hash")
                if autodb_attribute_id is not None and attribute.autodb_attribute_id != autodb_attribute_id:
                    attribute.autodb_attribute_id = autodb_attribute_id
                    updates.append("autodb_attribute_id")
            if updates:
                updates.append("updated_at")
                attribute.save(update_fields=tuple(dict.fromkeys(updates)))

        return attribute, created, reused, translation_pending

    def _ensure_value(
        self,
        *,
        attribute: Attribute,
        value: str,
        autodb_attribute_id: int | None,
        dry_run: bool,
    ) -> tuple[AttributeValue | None, bool]:
        clean_value = sanitize_product_name(value)
        if not clean_value:
            return None, False

        translation = self.translator.translate_product_name(source_text=clean_value)
        value_uk = translation.uk or clean_value
        value_ru = translation.ru or clean_value
        value_en = translation.en or clean_value
        translation_pending = translation.status != Product.NAME_TRANSLATION_TRANSLATED
        source_payload = {
            "source": "autodb_pro",
            "translation_status": "pending" if translation_pending else "translated",
            "value_source": clean_value,
            "autodb_attribute_id": autodb_attribute_id,
        }
        source_hash = sha1(json.dumps(source_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()  # noqa: S324

        cache_key = (str(attribute.id), clean_value.lower())
        value_obj = self._dry_run_value_cache.get(cache_key) if dry_run else None
        if value_obj is None:
            value_obj = AttributeValue.objects.filter(attribute=attribute, value=clean_value).order_by("id").first()
        if value_obj is None:
            value_obj = AttributeValue.objects.filter(attribute=attribute, value__iexact=clean_value).order_by("id").first()

        created = False
        if value_obj is None:
            value_obj = AttributeValue(
                attribute=attribute,
                value=clean_value,
                value_uk=value_uk,
                value_ru=value_ru,
                value_en=value_en,
                sort_order=0,
                autodb_attribute_id=autodb_attribute_id,
                source=AttributeValue.SOURCE_AUTODB_PRO,
                source_payload=source_payload,
                source_hash=source_hash,
            )
            created = True
            if not dry_run:
                value_obj.save()
            else:
                self._dry_run_value_cache[cache_key] = value_obj

        if value_obj is None:
            return None, created

        if not created and not dry_run:
            updates: list[str] = []
            if str(value_obj.source or "") != AttributeValue.SOURCE_MANUAL:
                if value_obj.value_uk != value_uk and value_uk:
                    value_obj.value_uk = value_uk
                    updates.append("value_uk")
                if value_obj.value_ru != value_ru and value_ru:
                    value_obj.value_ru = value_ru
                    updates.append("value_ru")
                if value_obj.value_en != value_en and value_en:
                    value_obj.value_en = value_en
                    updates.append("value_en")
                if str(value_obj.source or "") != AttributeValue.SOURCE_AUTODB_PRO:
                    value_obj.source = AttributeValue.SOURCE_AUTODB_PRO
                    updates.append("source")
                if value_obj.source_payload != source_payload:
                    value_obj.source_payload = source_payload
                    updates.append("source_payload")
                if str(value_obj.source_hash or "") != source_hash:
                    value_obj.source_hash = source_hash
                    updates.append("source_hash")
                if autodb_attribute_id is not None and value_obj.autodb_attribute_id != autodb_attribute_id:
                    value_obj.autodb_attribute_id = autodb_attribute_id
                    updates.append("autodb_attribute_id")
            if updates:
                updates.append("updated_at")
                value_obj.save(update_fields=tuple(dict.fromkeys(updates)))

        return value_obj, created

    def _generate_unique_slug(self, name: str) -> str:
        base = slugify(name) or "attribute"
        slug = base[:150]
        if not Attribute.objects.filter(slug=slug).exists():
            return slug
        suffix = 2
        while True:
            candidate = f"{base[:140]}-{suffix}"
            if not Attribute.objects.filter(slug=candidate).exists():
                return candidate
            suffix += 1

    def _find_article_attribute_rows(self, *, supplier_id: int, article_number: str) -> list[dict[str, Any]]:
        if supplier_id <= 0 or not article_number:
            return []

        self.storage.ensure_table("article_attributes")
        columns = list(self.storage.get_local_columns("article_attributes"))
        if not columns:
            return []

        supplier_column = find_column_name(columns, ["supplierid", "supplierId", "SupplierId", "supplier_id"])
        article_column = find_column_name(
            columns,
            [
                "datasupplierarticlenumber",
                "DataSupplierArticleNumber",
                "article",
                "articlenumber",
                "number",
            ],
        )
        if not supplier_column or not article_column:
            return []

        order_column = find_column_name(columns, ["id", "ID"])
        return self.storage.fetch_local_rows(
            table="article_attributes",
            filters={supplier_column: supplier_id, article_column: article_number},
            limit=1000,
            order_by=order_column,
            columns=columns,
        )

    def _safe_int(self, value: Any) -> int | None:
        try:
            if value is None or str(value).strip() == "":
                return None
            return int(value)
        except (TypeError, ValueError):
            return None
