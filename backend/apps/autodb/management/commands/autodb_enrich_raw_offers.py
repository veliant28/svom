from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.autodb.services.local_db_readiness import wait_for_local_autodb_ready
from apps.autodb.services.remote_config import AutoDbRemoteConfigError, AutoDbRemoteConfigValidator
from apps.autodb.services.raw_offer_enrichment import AutoDbRawOfferEnrichmentService, RawOfferEnrichmentSummary
from apps.supplier_imports.models import SupplierRawOffer


class Command(BaseCommand):
    help = "Bulk enrich existing SupplierRawOffer via Auto_DB_Pro (local-first) and link matched Products by composite key."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", action="append", default=[], help="Filter offers by supplier/source code (e.g. GPL, UTR).")
        parser.add_argument("--limit", type=int, default=0, help="Maximum raw offers to process.")
        parser.add_argument("--dry-run", action="store_true", help="Compute summary without persisting Product links or enrichment writes.")
        parser.add_argument("--allow-remote", action="store_true", help="Allow remote Auto-DB Pro fallback.")
        parser.add_argument("--only-unlinked", action="store_true", help="Only process offers with no linked Auto_DB_Pro key on matched product.")
        parser.add_argument("--only-matched-products", action="store_true", help="Only process offers that already have matched_product.")
        parser.add_argument("--batch-size", type=int, default=1000, help="Batch size for offers/pairs pipeline.")
        parser.add_argument("--no-remote", action="store_true", help="Disable remote Auto-DB Pro fallback for missing local pairs.")
        parser.add_argument("--enrich-related", action="store_true", help="Fetch related article_* rows in bulk for found composite keys.")
        parser.add_argument("--progress-every", type=int, default=0, help="Print progress every N processed pairs.")
        parser.add_argument(
            "--wait-for-autodb",
            type=int,
            default=0,
            help="Wait up to N seconds for local Auto_DB_Pro DB readiness before processing.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        allow_remote_flag = bool(options.get("allow_remote"))
        only_unlinked = bool(options.get("only_unlinked"))
        only_matched_products = bool(options.get("only_matched_products"))
        batch_size = max(int(options.get("batch_size") or 1000), 20)
        limit = max(int(options.get("limit") or 0), 0)
        no_remote_flag = bool(options.get("no_remote"))
        enrich_related = bool(options.get("enrich_related"))
        progress_every = max(int(options.get("progress_every") or 0), 0)
        wait_for_autodb = max(int(options.get("wait_for_autodb") or 0), 0)
        remote_disabled_reason = ""

        supplier_codes = [str(item or "").strip().lower() for item in (options.get("supplier") or []) if str(item or "").strip()]
        if allow_remote_flag and no_remote_flag:
            raise CommandError("Use either --allow-remote or --no-remote, not both.")

        readiness = wait_for_local_autodb_ready(timeout_seconds=wait_for_autodb, interval_seconds=2.0)
        if not readiness.ready:
            raise CommandError(
                "Auto_DB_Pro local DB is not ready/recovering. Retry later. "
                f"host={readiness.host} port={readiness.port} database={readiness.database} "
                f"reason={readiness.reason} attempts={readiness.attempts} waited_seconds={readiness.waited_seconds} "
                f"error={readiness.error_message or '-'}"
            )

        remote_enabled = bool(getattr(settings, "AUTODB_PRO_REMOTE_ENABLED", False))
        remote_lookup_enabled = bool(getattr(settings, "AUTODB_PRO_SUPPLIER_IMPORT_REMOTE_LOOKUP_ENABLED", False))

        requested_remote = False
        if no_remote_flag:
            remote_disabled_reason = "flag_no_remote"
        elif dry_run:
            requested_remote = allow_remote_flag
            if not allow_remote_flag:
                remote_disabled_reason = "dry_run_requires_allow_remote"
        else:
            requested_remote = allow_remote_flag or remote_lookup_enabled
            if not requested_remote:
                remote_disabled_reason = "setting_remote_lookup_disabled"

        allow_remote = remote_enabled and requested_remote
        if requested_remote and not remote_enabled:
            remote_disabled_reason = "global_remote_disabled"

        if allow_remote:
            try:
                AutoDbRemoteConfigValidator.ensure_remote_ready(allow_remote=True)
            except AutoDbRemoteConfigError as exc:
                allow_remote = False
                remote_disabled_reason = f"remote_config_error:{exc}"

        if dry_run and not allow_remote:
            self.stdout.write("Dry-run mode: remote Auto-DB fallback is disabled unless --allow-remote is set.")
        if not remote_enabled:
            self.stdout.write("Remote Auto-DB Pro is globally disabled in settings; command will run local-only.")

        offer_qs = self._build_offer_queryset(
            supplier_codes=supplier_codes,
            only_unlinked=only_unlinked,
            only_matched_products=only_matched_products,
        )
        if limit > 0:
            offer_qs = offer_qs[:limit]

        self.stdout.write(
            "Auto_DB_Pro raw offers enrichment started "
            f"dry_run={dry_run} allow_remote={allow_remote} batch_size={batch_size} enrich_related={enrich_related} "
            f"wait_for_autodb={wait_for_autodb}"
        )

        service = AutoDbRawOfferEnrichmentService()
        summary = service.run(
            offers=offer_qs.iterator(chunk_size=batch_size),
            dry_run=dry_run,
            allow_remote=allow_remote,
            remote_disabled_reason=remote_disabled_reason,
            enrich_related=enrich_related,
            batch_size=batch_size,
            progress_every=progress_every,
            progress_callback=self._on_progress if progress_every > 0 else None,
        )

        self._print_summary(
            summary=summary,
            dry_run=dry_run,
            allow_remote=allow_remote,
            enrich_related=enrich_related,
        )

    def _build_offer_queryset(self, *, supplier_codes: list[str], only_unlinked: bool, only_matched_products: bool):
        qs = SupplierRawOffer.objects.select_related("matched_product", "source", "supplier").order_by("id")
        if supplier_codes:
            supplier_filter = Q()
            for code in supplier_codes:
                supplier_filter |= Q(source__code__iexact=code)
                supplier_filter |= Q(supplier__code__iexact=code)
            qs = qs.filter(supplier_filter)

        if only_matched_products:
            qs = qs.filter(matched_product__isnull=False)

        if only_unlinked:
            qs = qs.filter(Q(matched_product__isnull=True) | Q(matched_product__autodb_article_key=""))

        return qs

    def _on_progress(
        self,
        *,
        processed_pairs: int,
        total_pairs: int,
        local_hits: int,
        remote_hits: int,
        missing: int,
        enriched: int,
        linked: int,
        elapsed_seconds: float,
        rate: float,
        eta_seconds: float,
    ) -> None:
        self.stdout.write(
            "progress "
            f"pairs={processed_pairs}/{total_pairs} local_hits={local_hits} remote_hits={remote_hits} "
            f"missing={missing} enriched={enriched} linked={linked} "
            f"elapsed={elapsed_seconds:.1f}s rate={rate:.2f}/s eta={eta_seconds:.1f}s"
        )

    def _print_summary(self, *, summary: RawOfferEnrichmentSummary, dry_run: bool, allow_remote: bool, enrich_related: bool) -> None:
        self.stdout.write("Auto_DB_Pro raw offers enrichment summary:")
        self.stdout.write(f"- total raw offers: {summary.total_raw_offers}")
        self.stdout.write(f"- unique pairs: {summary.unique_pairs}")
        self.stdout.write(f"- local hits: {summary.local_hits}")
        self.stdout.write(f"- remote hits: {summary.remote_hits}")
        self.stdout.write(f"- not found: {summary.not_found}")
        self.stdout.write(f"- failed: {summary.failed}")
        self.stdout.write(f"- enriched articles: {summary.enriched_articles}")
        self.stdout.write(f"- linked products: {summary.linked_products}")
        self.stdout.write(f"- skipped no matched_product: {summary.skipped_no_matched_product}")
        self.stdout.write(f"- skipped disabled/no remote: {summary.skipped_disabled_no_remote}")
        self.stdout.write(f"- remote_enabled: {summary.remote_enabled}")
        self.stdout.write(f"- remote_attempted: {summary.remote_attempted}")
        self.stdout.write(f"- remote_queries: {summary.remote_queries}")
        self.stdout.write(f"- remote_hits: {summary.remote_hits}")
        self.stdout.write(f"- remote_errors: {summary.remote_errors}")
        self.stdout.write(f"- remote_disabled_reason: {summary.remote_disabled_reason or '-'}")
        self.stdout.write(f"- elapsed seconds: {summary.elapsed_seconds:.3f}")
        self.stdout.write("- UTR calls: 0")
        if dry_run:
            self.stdout.write("- mode: dry-run (no Product/SupplierRawOffer writes)")
        self.stdout.write("- lookup mode: local-first with remote fallback" if allow_remote else "- lookup mode: local-only")
        if enrich_related and dry_run:
            self.stdout.write("- enrich-related: requested but skipped in dry-run")
