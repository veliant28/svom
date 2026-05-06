from __future__ import annotations

from dataclasses import asdict, dataclass

from django.conf import settings

from apps.autodb.services.product_name_enrichment import AutoDbProductNameEnrichmentService
from apps.autodb.services.product_image_enrichment import AutoDbProductImageEnrichmentService
from apps.autodb.services.raw_offer_enrichment import AutoDbRawOfferEnrichmentService, RawOfferEnrichmentSummary
from apps.autodb.services.remote_config import AutoDbRemoteConfigError, AutoDbRemoteConfigValidator
from apps.catalog.models import Product
from apps.supplier_imports.models import ImportRun, SupplierRawOffer
from apps.supplier_imports.services.gpl_images import GplProductImageService


@dataclass
class SupplierImportAutoDbSummary:
    enabled: bool = False
    name_update_enabled: bool = False
    limit: int = 0
    dry_run: bool = False
    remote_enabled: bool = False
    remote_attempted: bool = False
    remote_queries: int = 0
    remote_hits: int = 0
    remote_errors: int = 0
    remote_disabled_reason: str = ""
    remote_check_completed: bool = False
    remote_config_error: str = ""
    raw_offers_processed: int = 0
    unique_pairs: int = 0
    autodb_local_hits: int = 0
    autodb_remote_hits: int = 0
    not_found: int = 0
    failed: int = 0
    products_linked: int = 0
    product_names_updated: int = 0
    product_images_updated: int = 0
    gpl_images_created: int = 0
    autodb_images_created: int = 0
    stale_images_marked: int = 0
    names_skipped_manual_locked: int = 0
    names_skipped_no_autodb_title: int = 0
    translation_pending: int = 0
    translation_failed: int = 0
    elapsed_seconds: float = 0.0
    utr_catalog_calls: int = 0

    def to_dict(self) -> dict[str, int | bool | float | str]:
        return asdict(self)


class SupplierImportAutoDbPostProcessor:
    def __init__(
        self,
        *,
        raw_offer_enrichment_service: AutoDbRawOfferEnrichmentService | None = None,
        product_name_service: AutoDbProductNameEnrichmentService | None = None,
        gpl_image_service: GplProductImageService | None = None,
        autodb_image_service: AutoDbProductImageEnrichmentService | None = None,
    ):
        self.raw_offer_enrichment_service = raw_offer_enrichment_service or AutoDbRawOfferEnrichmentService()
        self.product_name_service = product_name_service or AutoDbProductNameEnrichmentService()
        self.gpl_image_service = gpl_image_service or GplProductImageService()
        self.autodb_image_service = autodb_image_service or AutoDbProductImageEnrichmentService()

    def run_for_import(
        self,
        *,
        run: ImportRun,
        dry_run: bool,
        autodb_enrich: bool,
        update_product_names: bool,
        update_product_images: bool = False,
        limit: int = 0,
        allow_remote_lookup: bool | None = None,
    ) -> SupplierImportAutoDbSummary:
        summary = SupplierImportAutoDbSummary(
            enabled=autodb_enrich,
            name_update_enabled=update_product_names,
            limit=max(int(limit or 0), 0),
            dry_run=bool(dry_run),
        )

        offer_qs = self._build_offers_queryset(run=run)
        if summary.limit > 0:
            selected_ids = list(offer_qs.values_list("id", flat=True)[: summary.limit])
            offer_qs = offer_qs.filter(id__in=selected_ids).order_by("id")
        summary.raw_offers_processed = offer_qs.count()
        if summary.raw_offers_processed <= 0:
            return summary

        if autodb_enrich:
            remote_enabled, remote_check_completed, remote_error, remote_disabled_reason = self._resolve_remote_capability(
                dry_run=dry_run,
                allow_remote_lookup=allow_remote_lookup,
            )
            summary.remote_enabled = remote_enabled
            summary.remote_check_completed = remote_check_completed
            summary.remote_config_error = remote_error
            summary.remote_disabled_reason = remote_disabled_reason

            raw_summary = self.raw_offer_enrichment_service.run(
                offers=offer_qs.iterator(chunk_size=500),
                dry_run=dry_run,
                allow_remote=remote_enabled,
                remote_disabled_reason=remote_disabled_reason,
                enrich_related=True,
                batch_size=500,
                progress_every=0,
                progress_callback=None,
            )
            self._merge_raw_summary(summary=summary, raw_summary=raw_summary)

        if update_product_names:
            linked_product_ids = self._collect_linked_product_ids(offer_qs=offer_qs)
            self._update_product_names(
                summary=summary,
                product_ids=linked_product_ids,
                dry_run=dry_run,
            )
        else:
            linked_product_ids = self._collect_linked_product_ids(offer_qs=offer_qs)

        if update_product_images:
            self._update_product_images(
                summary=summary,
                run=run,
                product_ids=linked_product_ids,
                dry_run=dry_run,
            )

        return summary

    def _build_offers_queryset(self, *, run: ImportRun):
        qs = (
            SupplierRawOffer.objects.select_related("matched_product", "matched_product__brand", "source", "supplier")
            .filter(run=run, matched_product__isnull=False)
            .order_by("id")
        )
        return qs

    def _resolve_remote_capability(
        self,
        *,
        dry_run: bool,
        allow_remote_lookup: bool | None,
    ) -> tuple[bool, bool, str, str]:
        remote_enabled_global = bool(getattr(settings, "AUTODB_PRO_REMOTE_ENABLED", False))
        remote_lookup_enabled = bool(getattr(settings, "AUTODB_PRO_SUPPLIER_IMPORT_REMOTE_LOOKUP_ENABLED", False))

        requested_remote = False
        remote_disabled_reason = ""

        if allow_remote_lookup is False:
            remote_disabled_reason = "flag_no_remote"
        elif dry_run:
            requested_remote = allow_remote_lookup is True
            if not requested_remote:
                remote_disabled_reason = "dry_run_requires_explicit_remote"
        else:
            requested_remote = (allow_remote_lookup is True) or remote_lookup_enabled
            if not requested_remote:
                remote_disabled_reason = "setting_remote_lookup_disabled"

        if not requested_remote:
            return False, False, "", remote_disabled_reason

        if not remote_enabled_global:
            return False, False, "", "global_remote_disabled"

        try:
            AutoDbRemoteConfigValidator.ensure_remote_ready(allow_remote=True)
        except AutoDbRemoteConfigError as exc:
            return False, False, str(exc), f"remote_config_error:{exc}"
        return True, True, "", ""

    def _merge_raw_summary(self, *, summary: SupplierImportAutoDbSummary, raw_summary: RawOfferEnrichmentSummary) -> None:
        summary.unique_pairs = raw_summary.unique_pairs
        summary.autodb_local_hits = raw_summary.local_hits
        summary.autodb_remote_hits = raw_summary.remote_hits
        summary.remote_attempted = raw_summary.remote_attempted
        summary.remote_queries = raw_summary.remote_queries
        summary.remote_hits = raw_summary.remote_hits
        summary.remote_errors = raw_summary.remote_errors
        if raw_summary.remote_disabled_reason:
            summary.remote_disabled_reason = raw_summary.remote_disabled_reason
        summary.not_found = raw_summary.not_found
        summary.failed += raw_summary.failed
        summary.products_linked = raw_summary.linked_products
        summary.elapsed_seconds = raw_summary.elapsed_seconds

    def _collect_linked_product_ids(self, *, offer_qs) -> list[str]:
        product_ids = (
            offer_qs.filter(matched_product__autodb_supplier_id__isnull=False)
            .exclude(matched_product__autodb_article_number="")
            .values_list("matched_product_id", flat=True)
            .distinct()
        )
        return [str(item) for item in product_ids if item]

    def _update_product_names(
        self,
        *,
        summary: SupplierImportAutoDbSummary,
        product_ids: list[str],
        dry_run: bool,
    ) -> None:
        if not product_ids:
            return

        products = Product.objects.filter(id__in=product_ids).select_related("brand", "category").order_by("id")
        for product in products.iterator(chunk_size=200):
            if bool(product.name_manually_locked):
                summary.names_skipped_manual_locked += 1
                continue

            diagnostics = self.product_name_service.build_diagnostics(product=product)
            if diagnostics.source_kind != Product.NAME_SOURCE_AUTODB_PRO or not diagnostics.source_title_after_cleanup:
                summary.names_skipped_no_autodb_title += 1
                continue

            result = self.product_name_service.enrich_product(
                product=product,
                dry_run=dry_run,
                only_missing_translations=False,
            )
            if result.status == "updated":
                summary.product_names_updated += 1
            elif result.status == "skipped_manual_locked":
                summary.names_skipped_manual_locked += 1
            elif result.status == "skipped_no_source_title":
                summary.names_skipped_no_autodb_title += 1

            if result.translation_status == Product.NAME_TRANSLATION_PENDING:
                summary.translation_pending += 1
            if result.translation_status == Product.NAME_TRANSLATION_FAILED:
                summary.translation_failed += 1

    def _update_product_images(
        self,
        *,
        summary: SupplierImportAutoDbSummary,
        run: ImportRun,
        product_ids: list[str],
        dry_run: bool,
    ) -> None:
        if not product_ids:
            return

        products = Product.objects.filter(id__in=product_ids).select_related("brand", "category").order_by("id")
        for product in products.iterator(chunk_size=200):
            if str(getattr(run.source, "code", "") or "").lower() == "gpl":
                gpl_result = self.gpl_image_service.sync_product_images(product=product, dry_run=dry_run)
                summary.gpl_images_created += gpl_result.created
                summary.stale_images_marked += gpl_result.stale_marked
                if gpl_result.created > 0 or gpl_result.stale_marked > 0:
                    summary.product_images_updated += 1

            autodb_result = self.autodb_image_service.sync_product_images(
                product=product,
                dry_run=dry_run,
                prefer_gpl=True,
            )
            summary.autodb_images_created += autodb_result.created
            summary.stale_images_marked += autodb_result.stale_marked
            if autodb_result.created > 0 or autodb_result.stale_marked > 0:
                summary.product_images_updated += 1
