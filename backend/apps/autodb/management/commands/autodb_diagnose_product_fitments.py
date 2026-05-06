from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services.local_db_readiness import wait_for_local_autodb_ready
from apps.autodb.services.product_fitment_enrichment import AutoDbProductFitmentEnrichmentService
from apps.catalog.models import Product


class Command(BaseCommand):
    help = "Diagnose Product fitment enrichment from local Auto_DB_Pro article_li rows."

    def add_arguments(self, parser):
        parser.add_argument("--product-id", required=True, help="Product UUID")
        parser.add_argument(
            "--wait-for-autodb",
            type=int,
            default=0,
            help="Wait up to N seconds for local Auto_DB_Pro DB readiness before diagnostics.",
        )

    def handle(self, *args, **options):
        product_id = str(options.get("product_id") or "").strip()
        wait_for_autodb = max(int(options.get("wait_for_autodb") or 0), 0)
        if not product_id:
            raise CommandError("--product-id is required")

        readiness = wait_for_local_autodb_ready(timeout_seconds=wait_for_autodb, interval_seconds=2.0)
        if not readiness.ready:
            raise CommandError(
                "Auto_DB_Pro local DB is not ready/recovering. Retry later. "
                f"host={readiness.host} port={readiness.port} database={readiness.database} "
                f"reason={readiness.reason} attempts={readiness.attempts} waited_seconds={readiness.waited_seconds} "
                f"error={readiness.error_message or '-'}"
            )

        try:
            product = Product.objects.select_related("brand", "category").get(pk=product_id)
        except Product.DoesNotExist as exc:
            raise CommandError(f"Product not found: {product_id}") from exc

        service = AutoDbProductFitmentEnrichmentService()
        diagnostics = service.build_diagnostics(product=product)

        self.stdout.write("Auto_DB_Pro product fitment diagnostics:")
        self.stdout.write(f"- product_id: {product.id}")
        self.stdout.write(f"- product_name: {product.name or '-'}")
        self.stdout.write(f"- bridge.autodb_supplier_id: {diagnostics.bridge_supplier_id or '-'}")
        self.stdout.write(f"- bridge.autodb_article_number: {diagnostics.bridge_article_number or '-'}")
        self.stdout.write(f"- bridge.autodb_article_key: {diagnostics.bridge_article_key or '-'}")

        self.stdout.write("- article_li rows:")
        if not diagnostics.article_li_rows:
            self.stdout.write("  - -")
        for row in diagnostics.article_li_rows:
            self.stdout.write(
                "  - "
                f"supplierId={row.get('supplierId') or row.get('supplierid') or '-'} "
                f"DataSupplierArticleNumber={row.get('DataSupplierArticleNumber') or row.get('datasupplierarticlenumber') or '-'} "
                f"linkageTypeId={row.get('linkageTypeId') or row.get('linkagetypeid') or '-'} "
                f"linkageId={row.get('linkageId') or row.get('linkageid') or '-'}"
            )

        self.stdout.write("- passenger car linkage candidates:")
        if not diagnostics.passenger_candidates:
            self.stdout.write("  - -")
        for row in diagnostics.passenger_candidates:
            self.stdout.write(
                "  - "
                f"supplierId={row.get('supplierId') or '-'} "
                f"DataSupplierArticleNumber={row.get('DataSupplierArticleNumber') or '-'} "
                f"linkageTypeId={row.get('linkageTypeId') or '-'} "
                f"linkageId={row.get('linkageId') or '-'}"
            )

        self.stdout.write("- passanger_cars rows for linkageId:")
        if not diagnostics.passanger_cars_rows:
            self.stdout.write("  - -")
        for row in diagnostics.passanger_cars_rows:
            self.stdout.write(
                "  - "
                f"id={row.get('id') or '-'} "
                f"modelid={row.get('modelid') or row.get('modelId') or '-'} "
                f"description={row.get('description') or '-'} "
                f"fulldescription={row.get('fulldescription') or row.get('fullDescription') or '-'}"
            )

        self.stdout.write("- current ProductFitments:")
        if not diagnostics.current_fitments:
            self.stdout.write("  - -")
        for row in diagnostics.current_fitments:
            self.stdout.write(
                "  - "
                f"id={row.get('id')} source={row.get('source') or '-'} modification_id={row.get('modification_id') or '-'} "
                f"autodb_passanger_car_id={row.get('autodb_passanger_car_id') or '-'} linkage_type={row.get('linkage_type') or '-'} "
                f"is_stale={bool(row.get('is_stale'))} manual_locked={bool(row.get('manual_locked'))}"
            )

        self.stdout.write("- proposed creates:")
        if not diagnostics.proposed_creates:
            self.stdout.write("  - -")
        for row in diagnostics.proposed_creates:
            self.stdout.write(
                "  - "
                f"source={row.get('source') or '-'} linkage_type={row.get('linkage_type') or '-'} "
                f"autodb_passanger_car_id={row.get('autodb_passanger_car_id') or '-'}"
            )

        self.stdout.write("- proposed updates:")
        if not diagnostics.proposed_updates:
            self.stdout.write("  - -")
        for row in diagnostics.proposed_updates:
            self.stdout.write(
                "  - "
                f"id={row.get('id') or '-'} manual_locked={bool(row.get('manual_locked'))} is_stale={bool(row.get('is_stale'))}"
            )

        self.stdout.write("- proposed stale marks:")
        if not diagnostics.proposed_stale:
            self.stdout.write("  - -")
        for row in diagnostics.proposed_stale:
            self.stdout.write(
                "  - "
                f"id={row.get('id') or '-'} autodb_passanger_car_id={row.get('autodb_passanger_car_id') or '-'} "
                f"manual_locked={bool(row.get('manual_locked'))}"
            )

        self.stdout.write("- reason if skipped:")
        self.stdout.write(f"  - {diagnostics.skipped_reason or 'not_skipped'}")
        self.stdout.write("- UTR calls: 0")
