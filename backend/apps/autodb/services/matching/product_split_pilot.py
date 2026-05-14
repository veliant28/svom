from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any

from django.db import transaction
from django.utils.text import slugify

from apps.autodb.models import AutoDbMatchEvidence, AutoDbMatchJob
from apps.catalog.models import AutoDbProductLinkQuality, Brand, Product
from apps.catalog.services.product_management import generate_unique_product_slug
from apps.pricing.models import ProductPrice, SupplierOffer
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_brand


def _canonical_article(value: str) -> str:
    return "".join(ch for ch in str(value or "").upper() if ch.isalnum())


@dataclass(frozen=True)
class AutoDbProductSplitPilotDryRun:
    sku: str
    source_product_id: str
    moved_offer_ids: tuple[str, ...]
    keep_group: str
    move_group: str
    proposed_new_sku: str
    proposed_new_slug: str
    proposed_new_name: str
    proposed_new_brand_id: str
    proposed_new_brand_name: str
    proposed_new_display_brand_name: str
    proposed_new_autodb_supplier_id: int | None
    proposed_new_article: str
    trusted_link_conflict: bool
    safety_blockers: tuple[str, ...]
    clean: bool


@dataclass(frozen=True)
class AutoDbProductSplitPilotApplyResult:
    sku: str
    source_product_id: str
    new_product_id: str
    moved_offer_ids: tuple[str, ...]
    productprice_action: str
    productprice_ids: tuple[str, ...]
    source_display_brand_name_after: str
    source_brand_source_after: str
    new_display_brand_name: str
    new_brand_source: str
    new_autodb_supplier_id: int | None
    source_trusted_link_count: int
    new_trusted_link_count: int
    rollback_fields: tuple[str, ...]


class AutoDbProductSplitPilotService:
    PRODUCT_SPLIT_EVIDENCE_STAGE = "product_split_pilot"
    QUARANTINE_SOURCE = "product_quality_quarantine"
    BRAND_SOURCE_HASH_MAX_LENGTH = 64

    def plan(
        self,
        *,
        sku: str,
        moved_offer_ids: list[str],
        keep_group: str,
        move_group: str,
    ) -> AutoDbProductSplitPilotDryRun:
        source = self._resolve_source_product(sku=sku)
        if source is None:
            return AutoDbProductSplitPilotDryRun(
                sku=sku,
                source_product_id="",
                moved_offer_ids=tuple(),
                keep_group=keep_group,
                move_group=move_group,
                proposed_new_sku="",
                proposed_new_slug="",
                proposed_new_name="",
                proposed_new_brand_id="",
                proposed_new_brand_name="",
                proposed_new_display_brand_name="",
                proposed_new_autodb_supplier_id=None,
                proposed_new_article="",
                trusted_link_conflict=False,
                safety_blockers=("source_product_not_found",),
                clean=False,
            )

        safety_blockers: list[str] = []
        source_product_id = str(source.id)

        moved_ids = [str(item or "").strip() for item in moved_offer_ids if str(item or "").strip()]
        moved_ids = sorted(set(moved_ids))
        if not moved_ids:
            safety_blockers.append("empty_moved_offer_ids")

        moved_offers = list(SupplierOffer.objects.select_related("supplier").filter(id__in=moved_ids))
        moved_offer_map = {str(item.id): item for item in moved_offers}
        if len(moved_offer_map) != len(moved_ids):
            safety_blockers.append("moved_offer_not_found")
        for oid, offer in moved_offer_map.items():
            if str(offer.product_id) != source_product_id:
                safety_blockers.append(f"offer_not_linked_to_source:{oid}")

        move_brand_norm, move_article = self._parse_group(move_group)
        keep_brand_norm, _keep_article = self._parse_group(keep_group)
        if not move_brand_norm or not move_article:
            safety_blockers.append("invalid_move_group")
        if not keep_brand_norm:
            safety_blockers.append("invalid_keep_group")

        brand = self._resolve_catalog_brand(move_brand_norm)
        if brand is None:
            safety_blockers.append("move_group_brand_not_resolved")
            brand_id = ""
            brand_name = ""
        else:
            brand_id = str(brand.id)
            brand_name = str(brand.name)

        product_price_count = ProductPrice.objects.filter(product=source).count()
        if product_price_count > 1:
            safety_blockers.append("ambiguous_productprice_relation")

        trusted_rows = list(
            AutoDbProductLinkQuality.objects.filter(product=source, status=AutoDbProductLinkQuality.STATUS_TRUSTED).values(
                "autodb_supplier_id",
            )
        )
        trusted_supplier_ids = {int(row.get("autodb_supplier_id") or 0) for row in trusted_rows if int(row.get("autodb_supplier_id") or 0) > 0}
        inferred_move_supplier = self._infer_autodb_supplier_id_for_move_group(source=source, move_brand_norm=move_brand_norm)
        trusted_link_conflict = bool(trusted_supplier_ids and inferred_move_supplier and inferred_move_supplier not in trusted_supplier_ids)
        if trusted_link_conflict:
            safety_blockers.append("trusted_link_conflict")

        raw_offer = self._latest_raw_offer_for_offer(source_product_id=source_product_id, offers=moved_offers)
        proposed_name = self._proposed_name(raw_offer=raw_offer, fallback_product=source, brand_name=brand_name, article=move_article)
        proposed_article = self._proposed_article(raw_offer=raw_offer, fallback=move_article)
        proposed_sku = self._generate_new_sku(source_sku=str(source.sku or ""))
        preferred_slug = slugify(f"{proposed_name}-{proposed_sku}")[:300]
        proposed_slug = generate_unique_product_slug(name=proposed_name, preferred_slug=preferred_slug)

        clean = len(safety_blockers) == 0
        return AutoDbProductSplitPilotDryRun(
            sku=sku,
            source_product_id=source_product_id,
            moved_offer_ids=tuple(moved_ids),
            keep_group=keep_group,
            move_group=move_group,
            proposed_new_sku=proposed_sku,
            proposed_new_slug=proposed_slug,
            proposed_new_name=proposed_name,
            proposed_new_brand_id=brand_id,
            proposed_new_brand_name=brand_name,
            proposed_new_display_brand_name=brand_name or move_brand_norm,
            proposed_new_autodb_supplier_id=inferred_move_supplier,
            proposed_new_article=proposed_article,
            trusted_link_conflict=trusted_link_conflict,
            safety_blockers=tuple(sorted(set(safety_blockers))),
            clean=clean,
        )

    def apply(
        self,
        *,
        sku: str,
        moved_offer_ids: list[str],
        keep_group: str,
        move_group: str,
    ) -> AutoDbProductSplitPilotApplyResult:
        plan = self.plan(sku=sku, moved_offer_ids=moved_offer_ids, keep_group=keep_group, move_group=move_group)
        if not plan.clean:
            raise RuntimeError(f"split pilot dry-run not clean: {list(plan.safety_blockers)}")

        source = Product.objects.select_related("brand", "category").get(id=plan.source_product_id)
        moved_offers = list(SupplierOffer.objects.select_related("supplier").filter(id__in=list(plan.moved_offer_ids), product=source))
        if len(moved_offers) != len(plan.moved_offer_ids):
            raise RuntimeError("moved offers changed after dry-run")

        new_brand = Brand.objects.get(id=plan.proposed_new_brand_id)
        rollback_fields = (
            "source_product_id",
            "new_product_id",
            "moved_offer_ids",
            "offer_product_previous",
            "offer_product_new",
        )

        with transaction.atomic():
            new_product = Product.objects.create(
                sku=plan.proposed_new_sku,
                svom_sku=None,
                article=plan.proposed_new_article,
                name=plan.proposed_new_name,
                slug=plan.proposed_new_slug,
                brand=new_brand,
                category=source.category,
                short_description=source.short_description,
                description=source.description,
                is_active=source.is_active,
                published_at=source.published_at,
                is_featured=False,
                is_new=False,
                is_bestseller=False,
                display_brand_name=plan.proposed_new_display_brand_name,
                normalized_brand=normalize_brand(plan.proposed_new_display_brand_name),
                normalized_article=_canonical_article(plan.proposed_new_article),
                brand_source=Product.BRAND_SOURCE_SUPPLIER_FALLBACK,
                brand_source_hash=self._brand_source_hash(kind="split_move", source_id=str(source.id), group=plan.move_group),
                brand_manually_locked=False,
                autodb_supplier_id=plan.proposed_new_autodb_supplier_id,
                autodb_supplier_name=plan.proposed_new_display_brand_name if plan.proposed_new_autodb_supplier_id else "",
                autodb_article_number=plan.proposed_new_article,
                autodb_article_key="",
                autodb_article_id=None,
                available_stock_qty_cached=0,
            )

            moved_offer_ids_out: list[str] = []
            for offer in moved_offers:
                offer.product = new_product
                offer.save(update_fields=["product", "updated_at"])
                moved_offer_ids_out.append(str(offer.id))

            source.display_brand_name = keep_group.split("|")[0]
            source.normalized_brand = normalize_brand(source.display_brand_name)
            source.brand_source = Product.BRAND_SOURCE_SUPPLIER_FALLBACK
            source.brand_source_hash = self._brand_source_hash(kind="split_keep", source_id=str(source.id), group=keep_group)
            source.save(
                update_fields=[
                    "display_brand_name",
                    "normalized_brand",
                    "brand_source",
                    "brand_source_hash",
                    "updated_at",
                ]
            )

            self._upsert_quarantine_job(product=source, status=AutoDbMatchJob.STATUS_NEEDS_REVIEW, reason=f"split_pilot_applied_source:{keep_group}")
            self._upsert_quarantine_job(product=new_product, status=AutoDbMatchJob.STATUS_NEEDS_REVIEW, reason=f"split_pilot_applied_new:{move_group}")
            self._append_split_evidence(product=source, status="source_retained", reason=f"keep_group={keep_group}", payload={"sku": sku})
            self._append_split_evidence(product=new_product, status="new_product_created", reason=f"move_group={move_group}", payload={"sku": sku, "moved_offer_ids": moved_offer_ids_out})

            source_trusted = AutoDbProductLinkQuality.objects.filter(product=source, status=AutoDbProductLinkQuality.STATUS_TRUSTED).count()
            new_trusted = AutoDbProductLinkQuality.objects.filter(product=new_product, status=AutoDbProductLinkQuality.STATUS_TRUSTED).count()

            price_ids = tuple(str(item.id) for item in ProductPrice.objects.filter(product=source).only("id"))
            return AutoDbProductSplitPilotApplyResult(
                sku=sku,
                source_product_id=str(source.id),
                new_product_id=str(new_product.id),
                moved_offer_ids=tuple(moved_offer_ids_out),
                productprice_action="no_reassign_no_recreate",
                productprice_ids=price_ids,
                source_display_brand_name_after=str(source.display_brand_name or ""),
                source_brand_source_after=str(source.brand_source or ""),
                new_display_brand_name=str(new_product.display_brand_name or ""),
                new_brand_source=str(new_product.brand_source or ""),
                new_autodb_supplier_id=int(new_product.autodb_supplier_id or 0) or None,
                source_trusted_link_count=source_trusted,
                new_trusted_link_count=new_trusted,
                rollback_fields=rollback_fields,
            )

    def _resolve_source_product(self, *, sku: str) -> Product | None:
        token = str(sku or "").strip()
        if not token:
            return None
        item = Product.objects.filter(svom_sku=token).first()
        if item is not None:
            return item
        return Product.objects.filter(sku=token).first()

    def _parse_group(self, group: str) -> tuple[str, str]:
        raw = str(group or "").strip()
        if "|" not in raw:
            return normalize_brand(raw), ""
        left, right = raw.split("|", 1)
        return normalize_brand(left), _canonical_article(right)

    def _resolve_catalog_brand(self, brand_norm: str) -> Brand | None:
        if not brand_norm:
            return None
        candidates = [item for item in Brand.objects.all().only("id", "name") if normalize_brand(str(item.name or "")) == brand_norm]
        if len(candidates) == 1:
            return candidates[0]
        return None

    def _infer_autodb_supplier_id_for_move_group(self, *, source: Product, move_brand_norm: str) -> int | None:
        source_autodb_name_norm = normalize_brand(str(source.autodb_supplier_name or ""))
        source_display_norm = normalize_brand(str(source.display_brand_name or ""))
        if move_brand_norm and (move_brand_norm == source_autodb_name_norm or move_brand_norm == source_display_norm):
            return int(source.autodb_supplier_id or 0) or None
        if move_brand_norm == "FEBIBILSTEIN":
            return 101
        if move_brand_norm == "POLMO":
            return 4873
        return None

    def _latest_raw_offer_for_offer(self, *, source_product_id: str, offers: list[SupplierOffer]) -> SupplierRawOffer | None:
        if not offers:
            return None
        out: SupplierRawOffer | None = None
        for offer in offers:
            item = (
                SupplierRawOffer.objects.filter(matched_product_id=source_product_id, supplier_id=offer.supplier_id, external_sku=offer.supplier_sku)
                .order_by("-updated_at", "-created_at")
                .first()
            )
            if item is not None:
                return item
            fallback = (
                SupplierRawOffer.objects.filter(matched_product_id=source_product_id, supplier_id=offer.supplier_id)
                .order_by("-updated_at", "-created_at")
                .first()
            )
            if fallback is not None:
                out = fallback
        return out

    def _proposed_name(self, *, raw_offer: SupplierRawOffer | None, fallback_product: Product, brand_name: str, article: str) -> str:
        if raw_offer is not None and str(raw_offer.product_name or "").strip():
            return str(raw_offer.product_name).strip()
        source_name = str(fallback_product.name or "").strip()
        if brand_name and article:
            return f"{brand_name} {article} ({source_name})".strip()
        if brand_name:
            return f"{brand_name} {source_name}".strip()
        return source_name or "Split product"

    def _proposed_article(self, *, raw_offer: SupplierRawOffer | None, fallback: str) -> str:
        if raw_offer is not None and str(raw_offer.article or "").strip():
            return str(raw_offer.article).strip()
        return str(fallback or "").strip()

    def _generate_new_sku(self, *, source_sku: str) -> str:
        max_len = Product._meta.get_field("sku").max_length
        base = str(source_sku or "").strip() or "SPLIT"
        base = base[: max_len - len("-SPLIT")]
        candidates = [f"{base}-SPLIT", f"{base}-SPLIT-2", f"{base}-SPLIT-3", f"{base}-SPLIT-4", f"{base}-SPLIT-5"]
        for item in candidates:
            item = item[:max_len]
            if not Product.objects.filter(sku=item).exists():
                return item
        suffix = 6
        while True:
            suffix_token = f"-SPLIT-{suffix}"
            item = f"{base[: max_len - len(suffix_token)]}{suffix_token}"
            if not Product.objects.filter(sku=item).exists():
                return item
            suffix += 1

    def _brand_source_hash(self, *, kind: str, source_id: str, group: str) -> str:
        token = f"{kind}:{source_id}:{group}"
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:24]
        value = f"{kind}:{digest}"
        return value[: self.BRAND_SOURCE_HASH_MAX_LENGTH]

    def _upsert_quarantine_job(self, *, product: Product, status: str, reason: str) -> AutoDbMatchJob:
        existing = (
            AutoDbMatchJob.objects.filter(
                product=product,
                supplier_offer__isnull=True,
                article_source_type=self.QUARANTINE_SOURCE,
            )
            .order_by("-updated_at", "-created_at")
            .first()
        )
        meta = {
            "quarantine": {
                "active": True,
                "source": "product_split_pilot",
                "status": status,
                "reason": reason,
            }
        }
        if existing is None:
            return AutoDbMatchJob.objects.create(
                product=product,
                supplier_offer=None,
                supplier_code="",
                raw_brand=str(product.display_brand_name or ""),
                normalized_brand=str(product.normalized_brand or ""),
                resolved_supplier_id=int(product.autodb_supplier_id or 0) or None,
                article_source_type=self.QUARANTINE_SOURCE,
                article_value="",
                canonical_article="",
                status=status,
                last_error=reason,
                metadata_json=meta,
            )
        existing.status = status
        existing.last_error = reason
        existing.metadata_json = meta
        existing.save(update_fields=["status", "last_error", "metadata_json", "updated_at"])
        return existing

    def _append_split_evidence(self, *, product: Product, status: str, reason: str, payload: dict[str, Any]) -> None:
        job = (
            AutoDbMatchJob.objects.filter(
                product=product,
                supplier_offer__isnull=True,
                article_source_type=self.QUARANTINE_SOURCE,
            )
            .order_by("-updated_at", "-created_at")
            .first()
        )
        if job is None:
            return
        AutoDbMatchEvidence.objects.create(
            job=job,
            stage=self.PRODUCT_SPLIT_EVIDENCE_STAGE,
            source="matching_service",
            result=status,
            supplier_id=int(product.autodb_supplier_id or 0) or None,
            article_value="",
            canonical_article="",
            reason=reason,
            payload_json=payload,
        )
