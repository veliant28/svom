from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
import json
import re
from typing import Any

from django.db.models import Q, QuerySet

from apps.autodb.services.column_helpers import find_column_name, find_value
from apps.autodb.services.prd_root_category_mapper import AutoDbPrdRootCategoryMapper
from apps.autodb.services.product_name_translation import ProductNameTranslationService
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.catalog.models import AutoDbPrdCategoryMap, Category, Product
from apps.catalog.services import (
    build_category_i18n_names,
    find_semantic_category_under_parent,
    generate_unique_category_slug,
    resolve_canonical_spec_for_name,
    sanitize_category_name,
)
from apps.catalog.services.taxonomy_v2 import find_seeded_leaf_by_name


@dataclass(frozen=True)
class ProductCategoryCandidate:
    prd_id: int
    source: str
    row: dict[str, Any]


@dataclass(frozen=True)
class ProductCategoryDiagnostics:
    product_id: str
    bridge_supplier_id: int | None
    bridge_article_number: str
    bridge_article_key: str
    article_prd_rows: tuple[dict[str, Any], ...]
    article_links_rows: tuple[dict[str, Any], ...]
    article_row: dict[str, Any]
    prd_rows: tuple[dict[str, Any], ...]
    autodb_article_title: str
    autodb_prd_title: str
    chosen_prd_id: int | None
    chosen_source: str
    chosen_prd_row: dict[str, Any]
    current_category_id: str
    current_category_name: str
    current_category_source: str
    current_category_autodb_prd_id: int | None
    proposed_category_id: str
    proposed_category_name: str
    proposed_category_source: str
    proposed_category_autodb_prd_id: int | None
    suspicious_link: bool
    suspicious_reason: str
    skipped_reason: str


@dataclass(frozen=True)
class ProductCategoryEnrichmentResult:
    product_id: str
    status: str
    old_category_id: str
    old_category_name: str
    new_category_id: str
    new_category_name: str
    chosen_prd_id: int | None
    chosen_source: str
    mapped_root_slug: str = ""
    mapped_root_name: str = ""
    mapped_root_confidence: float = 0.0
    mapped_root_reason: str = ""
    autodb_article_title: str = ""
    autodb_prd_title: str = ""
    created_category: bool = False
    reused_category: bool = False
    parent_missing: bool = False
    translation_pending: bool = False
    suspicious_link: bool = False
    warning: str = ""
    error: str = ""


def _category_has_root(*, category: Category, root: Category) -> bool:
    current: Category | None = category
    seen: set[str] = set()
    while current is not None and str(current.id) not in seen:
        if current.id == root.id:
            return True
        seen.add(str(current.id))
        if current.parent_id is None:
            return False
        current = Category.objects.filter(id=current.parent_id).select_related("parent").first()
    return False


class AutoDbProductCategoryEnrichmentService:
    _token_re = re.compile(r"[A-Za-zА-Яа-яІіЇїЄєҐґ0-9]{2,}")

    def __init__(
        self,
        *,
        storage: AutoDbRawCloneStorage | None = None,
        translator: ProductNameTranslationService | None = None,
        root_mapper: AutoDbPrdRootCategoryMapper | None = None,
    ):
        self.storage = storage or AutoDbRawCloneStorage()
        self.translator = translator or ProductNameTranslationService()
        self.root_mapper = root_mapper or AutoDbPrdRootCategoryMapper()
        self._prd_row_cache: dict[int, dict[str, Any] | None] = {}
        self._dry_run_category_cache: dict[int, Category] = {}

    def build_queryset(
        self,
        *,
        only_linked: bool,
        only_missing: bool,
        product_id: str,
    ) -> QuerySet[Product]:
        qs = Product.objects.select_related("category", "category__parent").order_by("id")
        if only_linked:
            qs = qs.filter(autodb_supplier_id__isnull=False).exclude(autodb_article_number="")
        if only_missing:
            qs = qs.filter(
                Q(category__autodb_prd_id__isnull=True)
                | ~Q(category__source=Category.SOURCE_AUTODB_PRO)
            )
        if product_id:
            qs = qs.filter(pk=product_id)
        return qs

    def enrich_product(
        self,
        *,
        product: Product,
        dry_run: bool,
    ) -> ProductCategoryEnrichmentResult:
        old_category_id = str(product.category_id or "")
        old_category_name = str(getattr(product.category, "name", "") or "")

        if bool(product.category_manually_locked):
            return ProductCategoryEnrichmentResult(
                product_id=str(product.id),
                status="skipped_manual_locked",
                old_category_id=old_category_id,
                old_category_name=old_category_name,
                new_category_id=old_category_id,
                new_category_name=old_category_name,
                chosen_prd_id=None,
                chosen_source="",
            )

        current_category_source = str(getattr(product.category, "source", "") or "")
        if current_category_source == Category.SOURCE_MANUAL:
            return ProductCategoryEnrichmentResult(
                product_id=str(product.id),
                status="skipped_manual_locked",
                old_category_id=old_category_id,
                old_category_name=old_category_name,
                new_category_id=old_category_id,
                new_category_name=old_category_name,
                chosen_prd_id=None,
                chosen_source="",
            )

        supplier_id = self._safe_int(getattr(product, "autodb_supplier_id", None))
        article_number = str(getattr(product, "autodb_article_number", "") or "").strip()
        if supplier_id is None or not article_number:
            return ProductCategoryEnrichmentResult(
                product_id=str(product.id),
                status="skipped_no_autodb_link",
                old_category_id=old_category_id,
                old_category_name=old_category_name,
                new_category_id=old_category_id,
                new_category_name=old_category_name,
                chosen_prd_id=None,
                chosen_source="",
            )

        candidate, prd_rows, article_prd_rows, article_links_rows = self._resolve_candidate(
            supplier_id=supplier_id,
            article_number=article_number,
        )
        article_row = self._find_article_row(supplier_id=supplier_id, article_number=article_number)
        autodb_article_title = self._extract_article_title(article_row)
        autodb_prd_title = self._extract_prd_name(candidate.row) if candidate is not None else ""
        if candidate is None:
            return ProductCategoryEnrichmentResult(
                product_id=str(product.id),
                status="skipped_no_autodb_category",
                old_category_id=old_category_id,
                old_category_name=old_category_name,
                new_category_id=old_category_id,
                new_category_name=old_category_name,
                chosen_prd_id=None,
                chosen_source="",
                autodb_article_title=autodb_article_title,
                autodb_prd_title=autodb_prd_title,
            )

        root_mapping = self.root_mapper.resolve(
            prd_description=self._extract_prd_name(candidate.row),
            prd_normalized_description=self._extract_prd_normalized_name(candidate.row),
            prd_assembly_group_description=self._extract_prd_assembly_group_name(candidate.row),
            prd_usage_description=self._extract_prd_usage_description(candidate.row),
            product_display_name=str(getattr(product, "name", "") or ""),
            autodb_article_title=autodb_article_title,
        )
        if root_mapping.status != AutoDbPrdRootCategoryMapper.STATUS_MAPPED:
            return ProductCategoryEnrichmentResult(
                product_id=str(product.id),
                status="skipped_no_root_mapping",
                old_category_id=old_category_id,
                old_category_name=old_category_name,
                new_category_id=old_category_id,
                new_category_name=old_category_name,
                chosen_prd_id=candidate.prd_id,
                chosen_source=candidate.source,
                mapped_root_slug="",
                mapped_root_name="",
                mapped_root_confidence=0.0,
                mapped_root_reason=root_mapping.reason,
                autodb_article_title=autodb_article_title,
                autodb_prd_title=autodb_prd_title,
            )
        root_category = self.root_mapper.resolve_root_category(root_slug=root_mapping.root_slug)
        if root_category is None:
            return ProductCategoryEnrichmentResult(
                product_id=str(product.id),
                status="skipped_no_root_mapping",
                old_category_id=old_category_id,
                old_category_name=old_category_name,
                new_category_id=old_category_id,
                new_category_name=old_category_name,
                chosen_prd_id=candidate.prd_id,
                chosen_source=candidate.source,
                mapped_root_slug=root_mapping.root_slug,
                mapped_root_name=root_mapping.root_name,
                mapped_root_confidence=root_mapping.confidence,
                mapped_root_reason=f"missing_root_category:{root_mapping.reason}",
                autodb_article_title=autodb_article_title,
                autodb_prd_title=autodb_prd_title,
            )

        suspicious, suspicious_reason = self._detect_suspicious_link(
            product=product,
            autodb_article_title=autodb_article_title,
            autodb_prd_title=autodb_prd_title,
        )
        if suspicious:
            return ProductCategoryEnrichmentResult(
                product_id=str(product.id),
                status="skipped_suspicious_link",
                old_category_id=old_category_id,
                old_category_name=old_category_name,
                new_category_id=old_category_id,
                new_category_name=old_category_name,
                chosen_prd_id=candidate.prd_id,
                chosen_source=candidate.source,
                autodb_article_title=autodb_article_title,
                autodb_prd_title=autodb_prd_title,
                suspicious_link=True,
                warning=suspicious_reason,
            )

        category, created, reused, parent_missing, translation_pending = self._ensure_category_for_candidate(
            candidate=candidate,
            root_category=root_category,
            dry_run=dry_run,
            visited=None,
        )
        if category is None:
            return ProductCategoryEnrichmentResult(
                product_id=str(product.id),
                status="skipped_no_autodb_category",
                old_category_id=old_category_id,
                old_category_name=old_category_name,
                new_category_id=old_category_id,
                new_category_name=old_category_name,
                chosen_prd_id=candidate.prd_id,
                chosen_source=candidate.source,
                mapped_root_slug=root_mapping.root_slug,
                mapped_root_name=root_mapping.root_name,
                mapped_root_confidence=root_mapping.confidence,
                mapped_root_reason=root_mapping.reason,
                autodb_article_title=autodb_article_title,
                autodb_prd_title=autodb_prd_title,
                parent_missing=parent_missing,
                translation_pending=translation_pending,
            )

        if str(product.category_id) == str(category.id):
            return ProductCategoryEnrichmentResult(
                product_id=str(product.id),
                status="skipped_hash_unchanged",
                old_category_id=old_category_id,
                old_category_name=old_category_name,
                new_category_id=str(category.id),
                new_category_name=str(category.name or ""),
                chosen_prd_id=candidate.prd_id,
                chosen_source=candidate.source,
                mapped_root_slug=root_mapping.root_slug,
                mapped_root_name=root_mapping.root_name,
                mapped_root_confidence=root_mapping.confidence,
                mapped_root_reason=root_mapping.reason,
                autodb_article_title=autodb_article_title,
                autodb_prd_title=autodb_prd_title,
                created_category=created,
                reused_category=reused,
                parent_missing=parent_missing,
                translation_pending=translation_pending,
            )

        if not dry_run:
            product.category = category
            product.save(update_fields=("category", "updated_at"))

        return ProductCategoryEnrichmentResult(
            product_id=str(product.id),
            status="updated",
            old_category_id=old_category_id,
            old_category_name=old_category_name,
            new_category_id=str(category.id),
            new_category_name=str(category.name or ""),
            chosen_prd_id=candidate.prd_id,
            chosen_source=candidate.source,
            mapped_root_slug=root_mapping.root_slug,
            mapped_root_name=root_mapping.root_name,
            mapped_root_confidence=root_mapping.confidence,
            mapped_root_reason=root_mapping.reason,
            autodb_article_title=autodb_article_title,
            autodb_prd_title=autodb_prd_title,
            created_category=created,
            reused_category=reused,
            parent_missing=parent_missing,
            translation_pending=translation_pending,
        )

    def build_diagnostics(self, *, product: Product) -> ProductCategoryDiagnostics:
        supplier_id = self._safe_int(getattr(product, "autodb_supplier_id", None))
        article_number = str(getattr(product, "autodb_article_number", "") or "").strip()

        article_prd_rows: tuple[dict[str, Any], ...] = ()
        article_links_rows: tuple[dict[str, Any], ...] = ()
        article_row: dict[str, Any] = {}
        prd_rows: tuple[dict[str, Any], ...] = ()
        candidate: ProductCategoryCandidate | None = None
        suspicious_link = False
        suspicious_reason = ""
        skipped_reason = ""

        if supplier_id is None or not article_number:
            skipped_reason = "skipped_no_autodb_link"
        else:
            article_row = self._find_article_row(supplier_id=supplier_id, article_number=article_number) or {}
            candidate, prd_list, article_prd_list, article_links_list = self._resolve_candidate(
                supplier_id=supplier_id,
                article_number=article_number,
            )
            article_prd_rows = tuple(article_prd_list)
            article_links_rows = tuple(article_links_list)
            prd_rows = tuple(prd_list)
            if candidate is None:
                skipped_reason = "skipped_no_autodb_category"
            else:
                suspicious_link, suspicious_reason = self._detect_suspicious_link(
                    product=product,
                    autodb_article_title=self._extract_article_title(article_row),
                    autodb_prd_title=self._extract_prd_name(candidate.row),
                )
                if suspicious_link:
                    skipped_reason = "skipped_suspicious_link"

        current_category = getattr(product, "category", None)
        proposed = None
        proposed_name = ""
        proposed_source = ""
        proposed_prd_id = None
        if candidate is not None:
            proposed = Category.objects.filter(autodb_prd_id=candidate.prd_id).first()
            if proposed is not None:
                proposed_name = str(proposed.name or "")
                proposed_source = str(proposed.source or "")
                proposed_prd_id = self._safe_int(proposed.autodb_prd_id)

        return ProductCategoryDiagnostics(
            product_id=str(product.id),
            bridge_supplier_id=supplier_id,
            bridge_article_number=article_number,
            bridge_article_key=str(getattr(product, "autodb_article_key", "") or ""),
            article_prd_rows=article_prd_rows,
            article_links_rows=article_links_rows,
            article_row=dict(article_row),
            prd_rows=prd_rows,
            autodb_article_title=self._extract_article_title(article_row),
            autodb_prd_title=self._extract_prd_name(candidate.row) if candidate is not None else "",
            chosen_prd_id=candidate.prd_id if candidate is not None else None,
            chosen_source=candidate.source if candidate is not None else "",
            chosen_prd_row=dict(candidate.row) if candidate is not None else {},
            current_category_id=str(getattr(current_category, "id", "") or ""),
            current_category_name=str(getattr(current_category, "name", "") or ""),
            current_category_source=str(getattr(current_category, "source", "") or ""),
            current_category_autodb_prd_id=self._safe_int(getattr(current_category, "autodb_prd_id", None)),
            proposed_category_id=str(getattr(proposed, "id", "") or ""),
            proposed_category_name=proposed_name,
            proposed_category_source=proposed_source,
            proposed_category_autodb_prd_id=proposed_prd_id,
            suspicious_link=suspicious_link,
            suspicious_reason=suspicious_reason,
            skipped_reason=skipped_reason,
        )

    def _resolve_candidate(
        self,
        *,
        supplier_id: int,
        article_number: str,
    ) -> tuple[
        ProductCategoryCandidate | None,
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
    ]:
        article_prd_rows = self._find_article_prd_rows(supplier_id=supplier_id, article_number=article_number)
        article_links_rows = self._find_article_links_rows(supplier_id=supplier_id, article_number=article_number)

        prd_ids_from_article_prd = self._extract_product_ids(article_prd_rows)
        prd_ids_from_article_links = self._extract_product_ids(article_links_rows)

        ordered_prd_ids: list[int] = []
        for prd_id in prd_ids_from_article_prd + prd_ids_from_article_links:
            if prd_id not in ordered_prd_ids:
                ordered_prd_ids.append(prd_id)

        prd_rows = self._find_prd_rows(product_ids=ordered_prd_ids)
        prd_by_id = {
            self._safe_int(find_value(row, ["id", "productId", "productid", "ProductId", "prdid"])): row
            for row in prd_rows
        }

        for prd_id in prd_ids_from_article_prd:
            row = prd_by_id.get(prd_id)
            if not row:
                continue
            if not self._extract_prd_name(row):
                continue
            return ProductCategoryCandidate(prd_id=prd_id, source="article_prd", row=row), prd_rows, article_prd_rows, article_links_rows

        for prd_id in prd_ids_from_article_links:
            row = prd_by_id.get(prd_id)
            if not row:
                continue
            if not self._extract_prd_name(row):
                continue
            return ProductCategoryCandidate(prd_id=prd_id, source="article_links", row=row), prd_rows, article_prd_rows, article_links_rows

        return None, prd_rows, article_prd_rows, article_links_rows

    def _ensure_category_for_candidate(
        self,
        *,
        candidate: ProductCategoryCandidate,
        root_category: Category,
        dry_run: bool,
        visited: set[int] | None,
    ) -> tuple[Category | None, bool, bool, bool, bool]:
        if root_category.parent_id is not None or root_category.source != Category.SOURCE_MANUAL:
            return None, False, False, False, False

        prd_id = int(candidate.prd_id)
        row = candidate.row
        name_uk = self._extract_prd_name(row)
        if not name_uk:
            return None, False, False, False, False

        if visited is None:
            visited = set()
        if prd_id in visited:
            return None, False, False, True, False
        visited.add(prd_id)

        parent_missing = False
        translation_pending = False

        canonical_spec = resolve_canonical_spec_for_name(name_uk)
        if canonical_spec is not None and str(root_category.slug or "") == canonical_spec.root_slug:
            uk, ru, en = canonical_spec.name_uk, canonical_spec.name_ru, canonical_spec.name_en
            translated_ok = True
            translation_pending = False
        else:
            uk, ru, en, translated_ok = self._build_category_i18n(name_uk=name_uk)
            translation_pending = translation_pending or self._is_translation_pending(uk=uk, ru=ru, en=en)
            if not translated_ok:
                translation_pending = True
        display_name = ru or uk or name_uk

        source_payload = self._build_source_payload(row=row, source=candidate.source, translation_pending=translation_pending)
        source_hash = sha1(json.dumps(source_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()  # noqa: S324

        category = None
        if dry_run:
            category = self._dry_run_category_cache.get(prd_id)

        if category is None:
            category = Category.objects.filter(autodb_prd_id=prd_id).first()

        reused = category is not None
        created = False

        if category is None:
            mapped = AutoDbPrdCategoryMap.objects.filter(prd_id=prd_id).select_related("category").first()
            if mapped is not None:
                category = mapped.category
                reused = True

        if category is None:
            seeded_leaf = find_seeded_leaf_by_name(uk or name_uk)
            if seeded_leaf is not None and _category_has_root(category=seeded_leaf, root=root_category):
                category = seeded_leaf
                reused = True

        if category is None:
            category = find_semantic_category_under_parent(
                parent=root_category,
                name=uk or name_uk,
                include_inactive=True,
            )
            if category is not None:
                reused = True

        if category is None:
            category = self._find_existing_autodb_category_by_name(
                name=uk or name_uk,
                parent_id=str(root_category.id),
            )
            if category is not None:
                reused = True

        if category is None:
            preferred_slug = f"autodb-prd-{prd_id}"
            slug = generate_unique_category_slug(
                name=uk or name_uk,
                preferred_slug=preferred_slug,
            )
            category = Category(
                name=display_name,
                name_uk=uk,
                name_ru=ru,
                name_en=en,
                slug=slug,
                parent=root_category,
                autodb_prd_id=prd_id,
                source=Category.SOURCE_AUTODB_PRO,
                source_payload=source_payload,
                source_hash=source_hash,
                show_in_header=False,
                is_assignable=True,
                is_active=True,
            )
            created = True
            reused = False
            if not dry_run:
                category.save()
            else:
                self._dry_run_category_cache[prd_id] = category

        if category is None:
            return None, created, reused, parent_missing, translation_pending

        if not created and not dry_run:
            updates: list[str] = []
            if not category.autodb_prd_id:
                category.autodb_prd_id = prd_id
                updates.append("autodb_prd_id")
            if not category.is_active:
                category.is_active = True
                updates.append("is_active")
            if category.parent_id != root_category.id:
                category.parent = root_category
                updates.append("parent")
            if category.show_in_header:
                category.show_in_header = False
                updates.append("show_in_header")
            if not category.is_assignable:
                category.is_assignable = True
                updates.append("is_assignable")
            if sanitize_category_name(category.name_uk or category.name) != uk and uk:
                category.name_uk = uk
                updates.append("name_uk")
            if sanitize_category_name(category.name) != sanitize_category_name(display_name):
                category.name = display_name
                updates.append("name")
            if category.name_ru != ru and ru:
                category.name_ru = ru
                updates.append("name_ru")
            if category.name_en != en and en:
                category.name_en = en
                updates.append("name_en")
            if category.source != Category.SOURCE_MANUAL and category.source != Category.SOURCE_AUTODB_PRO:
                category.source = Category.SOURCE_AUTODB_PRO
                updates.append("source")
            if category.source != Category.SOURCE_MANUAL:
                if category.source_payload != source_payload:
                    category.source_payload = source_payload
                    updates.append("source_payload")
                if category.source_hash != source_hash:
                    category.source_hash = source_hash
                    updates.append("source_hash")
            if updates:
                updates.append("updated_at")
                category.save(update_fields=tuple(dict.fromkeys(updates)))

        if not dry_run:
            AutoDbPrdCategoryMap.objects.update_or_create(
                prd_id=prd_id,
                defaults={
                    "prd_name": (uk or name_uk)[:255],
                    "category": category,
                    "source": AutoDbPrdCategoryMap.SOURCE_AUTO,
                    "confidence": None,
                },
            )

        return category, created, reused, parent_missing, translation_pending

    def _find_existing_autodb_category_by_name(self, *, name: str, parent_id: str) -> Category | None:
        normalized_target = sanitize_category_name(name)
        if not normalized_target:
            return None
        normalized_target = " ".join(normalized_target.split()).casefold()
        qs = Category.objects.filter(source=Category.SOURCE_AUTODB_PRO)
        if parent_id:
            qs = qs.filter(parent_id=parent_id)
        else:
            qs = qs.filter(parent__isnull=True)

        for category in qs.order_by("created_at", "id"):
            candidate_name = sanitize_category_name(category.name_uk or category.name)
            candidate_normalized = " ".join(candidate_name.split()).casefold()
            if candidate_normalized == normalized_target:
                return category
        return None

    def _build_prd_candidate(self, *, prd_id: int, source: str) -> ProductCategoryCandidate | None:
        row = self._find_prd_row_by_id(prd_id)
        if not row:
            return None
        if not self._extract_prd_name(row):
            return None
        return ProductCategoryCandidate(prd_id=prd_id, source=source, row=row)

    @staticmethod
    def _extract_prd_normalized_name(row: dict[str, Any]) -> str:
        return sanitize_category_name(
            str(
                find_value(
                    row,
                    (
                        "normalizeddescription",
                        "NormalizedDescription",
                        "descriptionnormalized",
                    ),
                )
                or ""
            )
        )

    @staticmethod
    def _extract_prd_assembly_group_name(row: dict[str, Any]) -> str:
        return sanitize_category_name(
            str(
                find_value(
                    row,
                    (
                        "assemblygroupdescription",
                        "AssemblyGroupDescription",
                        "assemblygroup",
                        "AssemblyGroup",
                    ),
                )
                or ""
            )
        )

    @staticmethod
    def _extract_prd_usage_description(row: dict[str, Any]) -> str:
        return sanitize_category_name(
            str(
                find_value(
                    row,
                    (
                        "usagedescription",
                        "UsageDescription",
                        "usage_description",
                    ),
                )
                or ""
            )
        )

    def _extract_product_ids(self, rows: list[dict[str, Any]]) -> list[int]:
        out: list[int] = []
        for row in rows:
            value = self._safe_int(find_value(row, ["productId", "productid", "ProductId", "prdid", "prdId", "id"]))
            if value is None:
                continue
            if value not in out:
                out.append(value)
        return out

    def _extract_prd_name(self, row: dict[str, Any]) -> str:
        for key in [
            "fulldescription",
            "fullDescription",
            "normalizeddescription",
            "NormalizedDescription",
            "description",
            "Description",
            "name",
            "title",
        ]:
            value = sanitize_category_name(str(find_value(row, [key]) or ""))
            if value:
                return value[:180]
        return ""

    def _extract_article_title(self, row: dict[str, Any] | None) -> str:
        payload = row or {}
        for key in ["normalizeddescription", "NormalizedDescription", "description", "Description"]:
            value = sanitize_category_name(str(find_value(payload, [key]) or ""))
            if value:
                return value[:255]
        return ""

    def _build_category_i18n(self, *, name_uk: str) -> tuple[str, str, str, bool]:
        uk, ru, en = build_category_i18n_names(name_uk)
        pending_from_dict = self._is_translation_pending(uk=uk, ru=ru, en=en)
        if not pending_from_dict:
            return uk, ru, en, True

        translated = self.translator.translate_product_name(source_text=uk)
        if translated.status == Product.NAME_TRANSLATION_TRANSLATED:
            return translated.uk or uk, translated.ru or ru, translated.en or en, True
        return uk, ru, en, False

    def _build_source_payload(self, *, row: dict[str, Any], source: str, translation_pending: bool) -> dict[str, Any]:
        return {
            "source": source,
            "translation_status": "pending" if translation_pending else "translated",
            "prd": {
                "id": self._safe_int(find_value(row, ["id", "productId", "productid", "ProductId", "prdid"])),
                "parentid": self._safe_int(find_value(row, ["parentid", "parentId", "ParentId"])),
                "description": str(find_value(row, ["description", "Description"]) or "")[:255],
                "fulldescription": str(find_value(row, ["fulldescription", "fullDescription"]) or "")[:255],
            },
        }

    def _is_translation_pending(self, *, uk: str, ru: str, en: str) -> bool:
        clean_uk = sanitize_category_name(uk)
        if not clean_uk:
            return True
        return sanitize_category_name(ru) == clean_uk and sanitize_category_name(en) == clean_uk

    def _detect_suspicious_link(
        self,
        *,
        product: Product,
        autodb_article_title: str,
        autodb_prd_title: str,
    ) -> tuple[bool, str]:
        product_titles = [
            str(getattr(product, "name_uk", "") or ""),
            str(getattr(product, "name_ru", "") or ""),
            str(getattr(product, "name_en", "") or ""),
            str(getattr(product, "name", "") or ""),
        ]
        product_tokens_list = [self._tokenize(item) for item in product_titles if item]
        reference_base = autodb_article_title or autodb_prd_title
        if not product_tokens_list or not reference_base:
            return False, ""

        translated = self.translator.translate_product_name(source_text=reference_base)
        reference_titles = [autodb_article_title, autodb_prd_title, translated.uk, translated.ru, translated.en]
        reference_tokens_list = [self._tokenize(item) for item in reference_titles if item]
        reference_tokens_list = [tokens for tokens in reference_tokens_list if len(tokens) >= 2]
        if not reference_tokens_list:
            return False, ""

        product_tokens_list = [tokens for tokens in product_tokens_list if len(tokens) >= 2]
        if not product_tokens_list:
            return False, ""

        for p_tokens in product_tokens_list:
            for r_tokens in reference_tokens_list:
                if p_tokens.intersection(r_tokens):
                    return False, ""

        product_preview = " | ".join(item for item in product_titles if item)[:240]
        reference_preview = " | ".join(item for item in reference_titles if item)[:240]
        reason = f"product_name_vs_autodb_conflict product={product_preview} autodb={reference_preview}"
        return True, reason

    def _tokenize(self, value: str) -> set[str]:
        text = str(value or "").lower()
        raw = self._token_re.findall(text)
        out = {item for item in raw if len(item) >= 4 and not item.isdigit()}
        return out

    def _find_article_row(self, *, supplier_id: int, article_number: str) -> dict[str, Any] | None:
        if supplier_id <= 0 or not article_number:
            return None
        self.storage.ensure_table("articles")
        columns = list(self.storage.get_local_columns("articles"))
        if not columns:
            return None
        supplier_column = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id"])
        article_column = find_column_name(
            columns,
            [
                "DataSupplierArticleNumber",
                "datasupplierarticlenumber",
                "PartsDataSupplierArticleNumber",
                "partsdatasupplierarticlenumber",
                "article",
                "articlenumber",
                "number",
            ],
        )
        if not supplier_column or not article_column:
            return None
        rows = self.storage.fetch_local_rows(
            table="articles",
            filters={supplier_column: supplier_id, article_column: article_number},
            limit=1,
            columns=columns,
        )
        if not rows:
            return None
        return dict(rows[0])

    def _find_article_prd_rows(self, *, supplier_id: int, article_number: str) -> list[dict[str, Any]]:
        if supplier_id <= 0 or not article_number:
            return []
        self.storage.ensure_table("article_prd")
        columns = list(self.storage.get_local_columns("article_prd"))
        supplier_column = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id"])
        article_column = find_column_name(
            columns,
            [
                "DataSupplierArticleNumber",
                "datasupplierarticlenumber",
                "PartsDataSupplierArticleNumber",
                "partsdatasupplierarticlenumber",
                "article",
                "articlenumber",
                "number",
            ],
        )
        if not supplier_column or not article_column:
            return []
        return self.storage.fetch_local_rows(
            table="article_prd",
            filters={supplier_column: supplier_id, article_column: article_number},
            limit=300,
            columns=columns,
        )

    def _find_article_links_rows(self, *, supplier_id: int, article_number: str) -> list[dict[str, Any]]:
        if supplier_id <= 0 or not article_number:
            return []
        self.storage.ensure_table("article_links")
        columns = list(self.storage.get_local_columns("article_links"))
        supplier_column = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id"])
        article_column = find_column_name(
            columns,
            [
                "DataSupplierArticleNumber",
                "datasupplierarticlenumber",
                "PartsDataSupplierArticleNumber",
                "partsdatasupplierarticlenumber",
                "article",
                "articlenumber",
                "number",
            ],
        )
        if not supplier_column or not article_column:
            return []
        return self.storage.fetch_local_rows(
            table="article_links",
            filters={supplier_column: supplier_id, article_column: article_number},
            limit=300,
            columns=columns,
        )

    def _find_prd_rows(self, *, product_ids: list[int]) -> list[dict[str, Any]]:
        if not product_ids:
            return []
        self.storage.ensure_table("prd")
        columns = list(self.storage.get_local_columns("prd"))
        if not columns:
            return []
        id_column = find_column_name(columns, ["id", "productId", "productid", "ProductId", "prdid"])
        if not id_column:
            return []
        return self.storage.fetch_local_rows_in(
            table="prd",
            column=id_column,
            values=product_ids,
            limit=max(100, len(product_ids) * 2),
            columns=columns,
        )

    def _find_prd_row_by_id(self, prd_id: int) -> dict[str, Any] | None:
        cached = self._prd_row_cache.get(prd_id)
        if cached is not None:
            return dict(cached) if cached else None

        rows = self._find_prd_rows(product_ids=[prd_id])
        row = rows[0] if rows else None
        self._prd_row_cache[prd_id] = dict(row) if row else None
        return dict(row) if row else None

    def _safe_int(self, value: Any) -> int | None:
        try:
            if value is None or str(value).strip() == "":
                return None
            return int(value)
        except (TypeError, ValueError):
            return None
