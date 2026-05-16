from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import OperationalError, ProgrammingError

from apps.autodb.models import AutoDbMatchJob
from apps.catalog.models import Brand, Product
from apps.catalog.services.product_sku import get_product_display_sku
from apps.pricing.models import ProductPrice, SupplierOffer
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_brand


def _canonical_article(value: str) -> str:
    return "".join(ch for ch in str(value or "").upper() if ch.isalnum())


def _sku_token(value: str) -> str:
    token = str(value or "").strip().upper()
    return "".join(ch for ch in token if ch.isalnum() or ch in "-_.")


@dataclass(frozen=True)
class AutoDbProductSplitV2DryRunPlan:
    sku: str
    source_product_id: str
    keep_group: str
    move_group: str
    keep_brand_norm: str
    move_brand_norm: str
    move_article_canonical: str
    sku_strategy_known: bool
    proposed_internal_sku: str
    proposed_internal_sku_source: str
    proposed_public_sku_strategy: str
    proposed_public_sku_value: str
    source_brand_after: str
    source_display_brand_after: str
    source_autodb_supplier_id_after: int | None
    source_autodb_supplier_name_after: str
    new_brand_after: str
    new_display_brand_after: str
    new_autodb_supplier_id_after: int | None
    new_autodb_supplier_name_after: str
    offers_to_move: tuple[str, ...]
    offers_to_keep: tuple[str, ...]
    raw_offers_to_move: tuple[str, ...]
    raw_offers_to_keep: tuple[str, ...]
    source_productprice_ids: tuple[str, ...]
    split_productprice_ids_existing: tuple[str, ...]
    productprice_strategy: str
    productprice_actions: tuple[str, ...]
    expected_original_supplier_codes_after: tuple[str, ...]
    expected_new_supplier_codes_after: tuple[str, ...]
    expected_original_raw_source_codes_after: tuple[str, ...]
    expected_new_raw_source_codes_after: tuple[str, ...]
    rollback_steps: tuple[str, ...]
    blockers: tuple[str, ...]
    clean: bool


class AutoDbProductSplitV2Planner:
    """
    Dry-run only planner for split v2.

    This service does not write data.
    """

    def plan(
        self,
        *,
        sku: str,
        source_product_id: str,
        moved_offer_ids: list[str],
        keep_group: str,
        move_group: str,
    ) -> AutoDbProductSplitV2DryRunPlan:
        source = self._resolve_source(sku=sku, source_product_id=source_product_id)
        blockers: list[str] = []
        if source is None:
            return AutoDbProductSplitV2DryRunPlan(
                sku=sku,
                source_product_id=source_product_id,
                keep_group=keep_group,
                move_group=move_group,
                keep_brand_norm="",
                move_brand_norm="",
                move_article_canonical="",
                sku_strategy_known=False,
                proposed_internal_sku="",
                proposed_internal_sku_source="",
                proposed_public_sku_strategy="",
                proposed_public_sku_value="",
                source_brand_after="",
                source_display_brand_after="",
                source_autodb_supplier_id_after=None,
                source_autodb_supplier_name_after="",
                new_brand_after="",
                new_display_brand_after="",
                new_autodb_supplier_id_after=None,
                new_autodb_supplier_name_after="",
                offers_to_move=tuple(),
                offers_to_keep=tuple(),
                raw_offers_to_move=tuple(),
                raw_offers_to_keep=tuple(),
                source_productprice_ids=tuple(),
                split_productprice_ids_existing=tuple(),
                productprice_strategy="",
                productprice_actions=tuple(),
                expected_original_supplier_codes_after=tuple(),
                expected_new_supplier_codes_after=tuple(),
                expected_original_raw_source_codes_after=tuple(),
                expected_new_raw_source_codes_after=tuple(),
                rollback_steps=tuple(),
                blockers=("source_product_not_found",),
                clean=False,
            )

        keep_brand_norm, keep_article = self._parse_group(keep_group)
        move_brand_norm, move_article = self._parse_group(move_group)
        if not keep_brand_norm:
            blockers.append("invalid_keep_group")
        if not move_brand_norm or not move_article:
            blockers.append("invalid_move_group")

        moved_offer_ids_norm = tuple(sorted(set(str(item or "").strip() for item in moved_offer_ids if str(item or "").strip())))
        if not moved_offer_ids_norm:
            blockers.append("empty_moved_offer_ids")

        all_offers = list(SupplierOffer.objects.select_related("supplier").filter(product=source).order_by("id"))
        offer_map = {str(item.id): item for item in all_offers}
        offers_to_move = tuple(oid for oid in moved_offer_ids_norm if oid in offer_map)
        missing_offer_ids = sorted(set(moved_offer_ids_norm) - set(offers_to_move))
        if missing_offer_ids:
            blockers.append("moved_offer_not_on_source")
        offers_to_keep = tuple(str(item.id) for item in all_offers if str(item.id) not in set(offers_to_move))
        if not offers_to_keep:
            blockers.append("no_offers_left_on_source_after_split")

        source_price_rows = list(ProductPrice.objects.filter(product=source).only("id"))
        source_price_ids = tuple(str(item.id) for item in source_price_rows)
        if len(source_price_ids) > 1:
            blockers.append("ambiguous_productprice_relation")

        existing_split = None
        candidate_splits = list(
            Product.objects.filter(is_active=False)
            .exclude(id=source.id)
            .filter(sku__icontains=str(source.sku or ""))
            .filter(sku__icontains="SPLIT")
            .order_by("-updated_at")[:20]
        )
        for candidate in candidate_splits:
            if self._is_cleanup_ignored(product_id=str(candidate.id)):
                continue
            existing_split = candidate
            break
        split_price_ids_existing: tuple[str, ...] = tuple()
        if existing_split is not None:
            split_price_ids_existing = tuple(str(item.id) for item in ProductPrice.objects.filter(product=existing_split).only("id"))
            blockers.append("existing_inactive_split_product_cleanup_needed")
            if split_price_ids_existing:
                blockers.append("productprice_relation_ambiguous_existing_split_product")

        raw_to_move, raw_to_keep, raw_ambiguous = self._plan_raw_offer_reassignment(
            source=source,
            all_offers=all_offers,
            offers_to_move=offers_to_move,
            move_article=move_article,
        )
        if raw_ambiguous:
            blockers.append("raw_offer_relation_ambiguous")

        sku_known, proposed_internal_sku, sku_source = self._propose_internal_sku(source=source, moved_offers=[offer_map[oid] for oid in offers_to_move])
        if not sku_known:
            blockers.append("unknown_safe_sku_strategy")

        proposed_public_strategy = "allocate_svom_sku_on_create_then_activate"
        proposed_public_value = "<generated_on_apply>"

        keep_brand = self._resolve_catalog_brand(keep_brand_norm)
        move_brand = self._resolve_catalog_brand(move_brand_norm)
        if keep_brand is None:
            blockers.append("keep_brand_not_resolved")
        if move_brand is None:
            blockers.append("move_brand_not_resolved")

        source_autodb_id_after, source_autodb_name_after = self._resolve_source_autodb_after(
            source=source,
            keep_brand_norm=keep_brand_norm,
        )
        new_autodb_id_after, new_autodb_name_after = self._resolve_new_autodb_after(
            source=source,
            move_brand_norm=move_brand_norm,
        )
        if move_brand_norm and new_autodb_id_after is None:
            blockers.append("brand_display_conflict_unresolved_new_autodb_supplier")

        productprice_actions = (
            f"source_reprice_existing_productprice:{','.join(source_price_ids) if source_price_ids else '<create>'}",
            "new_create_or_reprice_productprice_from_moved_offers",
            "no_manual_price_value_override",
        )
        if not offers_to_move:
            blockers.append("empty_move_offer_set")

        expected_original_supplier_codes = tuple(
            sorted(
                {
                    str(getattr(getattr(offer, "supplier", None), "code", "") or "").strip().lower()
                    for offer in all_offers
                    if str(offer.id) in set(offers_to_keep)
                }
            )
        )
        expected_new_supplier_codes = tuple(
            sorted(
                {
                    str(getattr(getattr(offer, "supplier", None), "code", "") or "").strip().lower()
                    for offer in all_offers
                    if str(offer.id) in set(offers_to_move)
                }
            )
        )

        expected_original_raw_sources = tuple(
            sorted(
                {
                    str(getattr(getattr(item, "source", None), "code", "") or "").strip().lower()
                    for item in SupplierRawOffer.objects.filter(id__in=list(raw_to_keep)).select_related("source")
                }
            )
        )
        expected_new_raw_sources = tuple(
            sorted(
                {
                    str(getattr(getattr(item, "source", None), "code", "") or "").strip().lower()
                    for item in SupplierRawOffer.objects.filter(id__in=list(raw_to_move)).select_related("source")
                }
            )
        )

        rollback_steps = (
            "move_supplier_offers_back_to_source_product",
            "move_supplier_raw_offers_matched_product_back_to_source",
            "restore_source_brand_display_autodb_binding_fields",
            "delete_or_deactivate_new_split_product",
            "restore_productprice_links_and_rerun_reprice",
            "restore_service_quarantine_state",
        )

        clean = len(blockers) == 0
        return AutoDbProductSplitV2DryRunPlan(
            sku=sku,
            source_product_id=str(source.id),
            keep_group=keep_group,
            move_group=move_group,
            keep_brand_norm=keep_brand_norm,
            move_brand_norm=move_brand_norm,
            move_article_canonical=move_article,
            sku_strategy_known=sku_known,
            proposed_internal_sku=proposed_internal_sku,
            proposed_internal_sku_source=sku_source,
            proposed_public_sku_strategy=proposed_public_strategy,
            proposed_public_sku_value=proposed_public_value,
            source_brand_after=str(getattr(keep_brand, "name", "") or keep_brand_norm),
            source_display_brand_after=str(getattr(keep_brand, "name", "") or keep_brand_norm),
            source_autodb_supplier_id_after=source_autodb_id_after,
            source_autodb_supplier_name_after=source_autodb_name_after,
            new_brand_after=str(getattr(move_brand, "name", "") or move_brand_norm),
            new_display_brand_after=str(getattr(move_brand, "name", "") or move_brand_norm),
            new_autodb_supplier_id_after=new_autodb_id_after,
            new_autodb_supplier_name_after=new_autodb_name_after,
            offers_to_move=offers_to_move,
            offers_to_keep=offers_to_keep,
            raw_offers_to_move=raw_to_move,
            raw_offers_to_keep=raw_to_keep,
            source_productprice_ids=source_price_ids,
            split_productprice_ids_existing=split_price_ids_existing,
            productprice_strategy="reprice_source_and_create_or_reprice_new",
            productprice_actions=productprice_actions,
            expected_original_supplier_codes_after=expected_original_supplier_codes,
            expected_new_supplier_codes_after=expected_new_supplier_codes,
            expected_original_raw_source_codes_after=expected_original_raw_sources,
            expected_new_raw_source_codes_after=expected_new_raw_sources,
            rollback_steps=rollback_steps,
            blockers=tuple(sorted(set(blockers))),
            clean=clean,
        )

    def _resolve_source(self, *, sku: str, source_product_id: str) -> Product | None:
        by_id = str(source_product_id or "").strip()
        if by_id:
            item = Product.objects.filter(id=by_id).first()
            if item is not None:
                return item
        token = str(sku or "").strip()
        if not token:
            return None
        item = Product.objects.filter(svom_sku=token).first()
        if item is not None:
            return item
        return Product.objects.filter(sku=token).first()

    def _parse_group(self, raw_group: str) -> tuple[str, str]:
        raw = str(raw_group or "").strip()
        if "|" not in raw:
            return normalize_brand(raw), ""
        left, right = raw.split("|", 1)
        return normalize_brand(left), _canonical_article(right)

    def _resolve_catalog_brand(self, normalized_brand: str) -> Brand | None:
        if not normalized_brand:
            return None
        try:
            candidates = [
                item for item in Brand.objects.all().only("id", "name")
                if normalize_brand(str(item.name or "")) == normalized_brand
            ]
        except (OperationalError, ProgrammingError):
            return None
        if len(candidates) == 1:
            return candidates[0]
        return None

    def _propose_internal_sku(self, *, source: Product, moved_offers: list[SupplierOffer]) -> tuple[bool, str, str]:
        max_len = Product._meta.get_field("sku").max_length
        candidates: list[tuple[str, str]] = []
        for offer in moved_offers:
            raw = _sku_token(str(getattr(offer, "supplier_sku", "") or ""))
            if raw:
                candidates.append((raw, "moved_offer_supplier_sku"))
        for offer in moved_offers:
            raw = _sku_token(str(getattr(getattr(offer, "supplier", None), "code", "") or ""))
            if raw:
                candidates.append((f"{raw}-{_canonical_article(source.article or '')}", "supplier_code_plus_source_article"))
        base = _sku_token(str(source.sku or ""))
        if base:
            candidates.append((f"{base}-SV2", "source_sku_sv2_suffix"))

        tried: set[str] = set()
        for candidate, source_name in candidates:
            value = candidate[:max_len]
            if not value:
                continue
            if "SPLIT" in value.upper():
                continue
            if value in tried:
                continue
            tried.add(value)
            if not Product.objects.filter(sku=value).exists():
                return True, value, source_name
            # deterministic short suffix without SPLIT token
            for idx in range(2, 20):
                suffix = f"-SV2-{idx}"
                base_token = value[: max_len - len(suffix)]
                attempt = f"{base_token}{suffix}"
                if "SPLIT" in attempt.upper():
                    continue
                if Product.objects.filter(sku=attempt).exists():
                    continue
                return True, attempt, f"{source_name}_collision_retry"
        return False, "", ""

    def _plan_raw_offer_reassignment(
        self,
        *,
        source: Product,
        all_offers: list[SupplierOffer],
        offers_to_move: tuple[str, ...],
        move_article: str,
    ) -> tuple[tuple[str, ...], tuple[str, ...], bool]:
        move_offer_set = set(offers_to_move)
        moved_offers = [item for item in all_offers if str(item.id) in move_offer_set]
        raw_queryset = SupplierRawOffer.objects.filter(matched_product=source).select_related("supplier", "source")
        all_raw = list(raw_queryset.order_by("supplier__code", "-updated_at", "-id"))
        raw_to_move: set[str] = set()
        raw_ambiguous = False

        for offer in moved_offers:
            supplier_rows = [row for row in all_raw if row.supplier_id == offer.supplier_id]
            if not supplier_rows:
                raw_ambiguous = True
                continue
            sku_norm = _canonical_article(getattr(offer, "supplier_sku", ""))
            matched = []
            for row in supplier_rows:
                article_norm = _canonical_article(getattr(row, "article", ""))
                external_norm = _canonical_article(getattr(row, "external_sku", ""))
                normalized_article = _canonical_article(getattr(row, "normalized_article", ""))
                if move_article and (article_norm == move_article or external_norm == move_article or normalized_article == move_article):
                    matched.append(row)
                    continue
                if sku_norm and (article_norm == sku_norm or external_norm == sku_norm or normalized_article == sku_norm):
                    matched.append(row)
                    continue
            if not matched:
                # fallback is unsafe: supplier has rows but matching signal was not deterministic.
                raw_ambiguous = True
                continue
            for row in matched:
                raw_to_move.add(str(row.id))

        raw_to_keep = tuple(str(row.id) for row in all_raw if str(row.id) not in raw_to_move)
        return tuple(sorted(raw_to_move)), raw_to_keep, raw_ambiguous

    def _resolve_source_autodb_after(self, *, source: Product, keep_brand_norm: str) -> tuple[int | None, str]:
        current_name_norm = normalize_brand(str(source.autodb_supplier_name or ""))
        if keep_brand_norm and keep_brand_norm == current_name_norm:
            return int(source.autodb_supplier_id or 0) or None, str(source.autodb_supplier_name or "")
        # keep brand is different -> recommend clearing to avoid display precedence conflict.
        return None, ""

    def _resolve_new_autodb_after(self, *, source: Product, move_brand_norm: str) -> tuple[int | None, str]:
        current_name = str(source.autodb_supplier_name or "")
        current_norm = normalize_brand(current_name)
        if move_brand_norm and move_brand_norm == current_norm:
            return int(source.autodb_supplier_id or 0) or None, current_name
        return None, ""

    def preview_visibility(self, *, source_product: Product, plan: AutoDbProductSplitV2DryRunPlan) -> dict[str, Any]:
        return {
            "source_display_sku_now": get_product_display_sku(source_product),
            "new_display_sku_expected": plan.proposed_public_sku_value or plan.proposed_internal_sku,
            "source_brand_filter_expected": plan.source_brand_after,
            "new_brand_filter_expected": plan.new_brand_after,
            "source_supplier_codes_expected": list(plan.expected_original_supplier_codes_after),
            "new_supplier_codes_expected": list(plan.expected_new_supplier_codes_after),
            "source_raw_sources_expected": list(plan.expected_original_raw_source_codes_after),
            "new_raw_sources_expected": list(plan.expected_new_raw_source_codes_after),
        }

    def _is_cleanup_ignored(self, *, product_id: str) -> bool:
        rows = (
            AutoDbMatchJob.objects.filter(
                product_id=product_id,
                supplier_offer__isnull=True,
                article_source_type="product_quality_quarantine",
            )
            .values_list("metadata_json", flat=True)
            .order_by("-updated_at", "-created_at")[:10]
        )
        for payload in rows:
            if not isinstance(payload, dict):
                continue
            marker = payload.get("split_artifact_cleanup", {})
            if isinstance(marker, dict) and bool(marker.get("ignore_as_artifact")):
                return True
        return False
