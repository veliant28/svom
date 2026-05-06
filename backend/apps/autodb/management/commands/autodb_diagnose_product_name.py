from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services.product_name_enrichment import AutoDbProductNameEnrichmentService
from apps.catalog.models import Product


class Command(BaseCommand):
    help = "Diagnose Product name enrichment sources and cleanup decisions."

    def add_arguments(self, parser):
        parser.add_argument("--product-id", required=True, help="Product UUID")

    def handle(self, *args, **options):
        product_id = str(options.get("product_id") or "").strip()
        if not product_id:
            raise CommandError("--product-id is required")

        try:
            product = Product.objects.select_related("brand").get(pk=product_id)
        except Product.DoesNotExist as exc:
            raise CommandError(f"Product not found: {product_id}") from exc

        service = AutoDbProductNameEnrichmentService()
        diagnostics = service.build_diagnostics(product=product)
        translation = service.translator.translate_product_name(source_text=diagnostics.source_title_after_cleanup)

        self.stdout.write("Auto_DB_Pro product name diagnostics:")
        self.stdout.write(f"- product_id: {product.id}")
        self.stdout.write(f"- product_name_current: {product.name or '-'}")
        self.stdout.write(f"- name_uk_current: {product.name_uk or '-'}")
        self.stdout.write(f"- name_ru_current: {product.name_ru or '-'}")
        self.stdout.write(f"- name_en_current: {product.name_en or '-'}")
        self.stdout.write(f"- bridge.autodb_supplier_id: {product.autodb_supplier_id or '-'}")
        self.stdout.write(f"- bridge.autodb_article_number: {product.autodb_article_number or '-'}")
        self.stdout.write(f"- bridge.autodb_article_key: {product.autodb_article_key or '-'}")

        self.stdout.write("- linked_raw_offers:")
        if not diagnostics.raw_offer_rows:
            self.stdout.write("  - -")
        for row in diagnostics.raw_offer_rows:
            payload = row.get("raw_payload") if isinstance(row.get("raw_payload"), dict) else {}
            self.stdout.write(
                f"  - raw_offer_id={row.get('id')} article={row.get('article') or '-'} "
                f"external_sku={row.get('external_sku') or '-'} "
                f"payload_article={payload.get('Артикул') or '-'} "
                f"payload_article_utr={payload.get('Артикул UTR') or '-'} "
                f"payload_article_td={payload.get('Артикул ТД') or payload.get('article_td') or '-'}"
            )

        self.stdout.write("- autodb_rows:")
        self.stdout.write(
            f"  - articles.NormalizedDescription={diagnostics.article_row.get('NormalizedDescription') or diagnostics.article_row.get('normalizeddescription') or '-'}"
        )
        self.stdout.write(
            f"  - articles.Description={diagnostics.article_row.get('Description') or diagnostics.article_row.get('description') or '-'}"
        )

        self.stdout.write("  - article_prd rows:")
        if not diagnostics.article_prd_rows:
            self.stdout.write("    - -")
        for row in diagnostics.article_prd_rows:
            self.stdout.write(
                f"    - supplierid={row.get('supplierid') or row.get('supplierId') or '-'} "
                f"datasupplierarticlenumber={row.get('datasupplierarticlenumber') or row.get('DataSupplierArticleNumber') or '-'} "
                f"productId={row.get('productId') or row.get('productid') or '-'}"
            )

        self.stdout.write("  - article_links rows:")
        if not diagnostics.article_links_rows:
            self.stdout.write("    - -")
        for row in diagnostics.article_links_rows:
            self.stdout.write(
                f"    - supplierid={row.get('supplierid') or row.get('supplierId') or '-'} "
                f"datasupplierarticlenumber={row.get('datasupplierarticlenumber') or row.get('DataSupplierArticleNumber') or '-'} "
                f"productid={row.get('productid') or row.get('productId') or '-'}"
            )

        self.stdout.write("  - prd candidates:")
        if not diagnostics.prd_rows:
            self.stdout.write("    - -")
        for row in diagnostics.prd_rows:
            self.stdout.write(
                f"    - id={row.get('id') or '-'} normalizeddescription={row.get('normalizeddescription') or '-'} "
                f"description={row.get('description') or '-'}"
            )

        self.stdout.write("  - article_inf rows:")
        if not diagnostics.article_inf_rows:
            self.stdout.write("    - -")
        for row in diagnostics.article_inf_rows:
            self.stdout.write(
                f"    - InformationText={row.get('InformationText') or row.get('informationtext') or '-'}"
            )

        self.stdout.write(
            f"- suffix_candidates: {', '.join(diagnostics.suffix_candidates) if diagnostics.suffix_candidates else '-'}"
        )
        self.stdout.write(f"- chosen_source: {diagnostics.source_kind or '-'}")
        self.stdout.write(f"- source_reason: {diagnostics.source_reason or '-'}")
        self.stdout.write(f"- title_before_cleanup: {diagnostics.source_title_before_cleanup or '-'}")
        self.stdout.write(f"- title_after_cleanup: {diagnostics.source_title_after_cleanup or '-'}")
        self.stdout.write(f"- supplier_fallback_used: {diagnostics.supplier_fallback_used}")
        self.stdout.write(f"- supplier_fallback_reason: {diagnostics.supplier_fallback_reason or '-'}")

        self.stdout.write("- translation_preview:")
        self.stdout.write(f"  - status={translation.status}")
        self.stdout.write(f"  - uk={translation.uk or '-'}")
        self.stdout.write(f"  - ru={translation.ru or '-'}")
        self.stdout.write(f"  - en={translation.en or '-'}")
        if translation.error:
            self.stdout.write(f"  - error={translation.error}")

        self.stdout.write("- UTR calls: 0")
