from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services.product_image_enrichment import AutoDbProductImageEnrichmentService
from apps.autodb.services.local_db_readiness import wait_for_local_autodb_ready
from apps.catalog.models import Product, ProductImage
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.services.gpl_images import GplProductImageService


class Command(BaseCommand):
    help = "Diagnose Product image enrichment from GPL raw payload and Auto_DB_Pro article_images."

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
            product = Product.objects.select_related("brand", "category").prefetch_related("images").get(pk=product_id)
        except Product.DoesNotExist as exc:
            raise CommandError(f"Product not found: {product_id}") from exc

        gpl_service = GplProductImageService()
        autodb_service = AutoDbProductImageEnrichmentService()

        gpl_diag = gpl_service.build_diagnostics(product=product)
        autodb_diag = autodb_service.build_diagnostics(product=product)

        offers = list(
            SupplierRawOffer.objects.filter(matched_product=product)
            .select_related("source", "supplier")
            .order_by("-updated_at", "-id")[:10]
        )

        self.stdout.write("Auto_DB_Pro product image diagnostics:")
        self.stdout.write(f"- product_id: {product.id}")
        self.stdout.write(f"- product_name: {product.name or '-'}")
        self.stdout.write(f"- bridge.autodb_supplier_id: {autodb_diag.bridge_supplier_id or '-'}")
        self.stdout.write(f"- bridge.autodb_article_number: {autodb_diag.bridge_article_number or '-'}")
        self.stdout.write(f"- bridge.autodb_article_key: {autodb_diag.bridge_article_key or '-'}")

        self.stdout.write("- supplier/source offers:")
        if not offers:
            self.stdout.write("  - -")
        for offer in offers:
            self.stdout.write(
                f"  - raw_offer_id={offer.id} source={offer.source.code} supplier={offer.supplier.code} updated_at={offer.updated_at.isoformat()}"
            )

        self.stdout.write("- GPL image candidates from raw_payload:")
        self.stdout.write(f"  - source_code={gpl_diag.source_code or '-'} latest_offer_id={gpl_diag.latest_offer_id or '-'}")
        self.stdout.write(f"  - payload_keys={','.join(gpl_diag.payload_keys) if gpl_diag.payload_keys else '-'}")
        if not gpl_diag.candidates:
            self.stdout.write("  - candidate=-")
        for url in gpl_diag.candidates:
            self.stdout.write(f"  - candidate={url}")

        self.stdout.write("- Auto_DB_Pro article_images rows:")
        if not autodb_diag.article_images_rows:
            self.stdout.write("  - -")
        for row in autodb_diag.article_images_rows:
            self.stdout.write(
                f"  - supplierId={row.get('supplierId') or row.get('supplierid') or '-'} "
                f"DataSupplierArticleNumber={row.get('DataSupplierArticleNumber') or row.get('datasupplierarticlenumber') or '-'} "
                f"FileName={row.get('FileName') or row.get('filename') or '-'} "
                f"PictureName={row.get('PictureName') or row.get('picturename') or '-'} "
                f"TecdocHyperlinkName={row.get('TecdocHyperlinkName') or row.get('tecdocHyperlinkName') or '-'}"
            )

        self.stdout.write("- Auto_DB_Pro image candidates:")
        if not autodb_diag.candidates:
            self.stdout.write("  - candidate=-")
        for candidate in autodb_diag.candidates:
            self.stdout.write(
                "  - "
                f"remote_url={candidate.get('remote_url') or '-'} "
                f"reference_kind={candidate.get('reference_kind') or '-'} "
                f"reference={candidate.get('reference') or '-'} "
                f"pending_url_resolution={bool(candidate.get('pending_url_resolution'))}"
            )

        self.stdout.write("- current ProductImages:")
        images = list(product.images.order_by("sort_order", "id"))
        if not images:
            self.stdout.write("  - -")
        for image in images:
            self.stdout.write(
                f"  - id={image.id} source={image.source or '-'} is_primary={image.is_primary} is_stale={image.is_stale} "
                f"remote_url={image.remote_url or '-'} image_file={getattr(image.image, 'name', '') or '-'}"
            )

        proposed_primary, skipped_reason = self._resolve_primary_plan(
            images=images,
            gpl_candidates=bool(gpl_diag.candidates),
            autodb_candidates=bool(autodb_diag.candidates),
            has_autodb_link=bool(autodb_diag.bridge_supplier_id and autodb_diag.bridge_article_number),
        )

        self.stdout.write("- proposed primary image:")
        self.stdout.write(f"  - {proposed_primary}")
        self.stdout.write("- reason if skipped:")
        self.stdout.write(f"  - {skipped_reason}")
        self.stdout.write("- UTR calls: 0")

    def _resolve_primary_plan(
        self,
        *,
        images: list[ProductImage],
        gpl_candidates: bool,
        autodb_candidates: bool,
        has_autodb_link: bool,
    ) -> tuple[str, str]:
        manual_primary = next(
            (image for image in images if image.source == ProductImage.SOURCE_MANUAL and image.is_primary),
            None,
        )
        if manual_primary is not None:
            return f"manual:{manual_primary.id}", "skipped_manual_primary"

        if gpl_candidates:
            return "gpl_price:first_candidate", "not_skipped"
        if autodb_candidates:
            return "autodb_pro:first_candidate", "not_skipped"
        if not has_autodb_link:
            return "-", "skipped_no_autodb_link"
        return "-", "skipped_no_images"
