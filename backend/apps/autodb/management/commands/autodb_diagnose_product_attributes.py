from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services.product_attribute_enrichment import AutoDbProductAttributeEnrichmentService
from apps.catalog.models import Product


class Command(BaseCommand):
    help = "Diagnose Product attribute enrichment from local Auto_DB_Pro article_attributes rows."

    def add_arguments(self, parser):
        parser.add_argument("--product-id", required=True, help="Product UUID")

    def handle(self, *args, **options):
        product_id = str(options.get("product_id") or "").strip()
        if not product_id:
            raise CommandError("--product-id is required")

        try:
            product = Product.objects.select_related("brand", "category").prefetch_related(
                "product_attributes",
                "product_attributes__attribute",
                "product_attributes__attribute_value",
            ).get(pk=product_id)
        except Product.DoesNotExist as exc:
            raise CommandError(f"Product not found: {product_id}") from exc

        service = AutoDbProductAttributeEnrichmentService()
        diagnostics = service.build_diagnostics(product=product)

        self.stdout.write("Auto_DB_Pro product attribute diagnostics:")
        self.stdout.write(f"- product_id: {product.id}")
        self.stdout.write(f"- product_name: {product.name or '-'}")
        self.stdout.write(f"- bridge.autodb_supplier_id: {diagnostics.bridge_supplier_id or '-'}")
        self.stdout.write(f"- bridge.autodb_article_number: {diagnostics.bridge_article_number or '-'}")
        self.stdout.write(f"- bridge.autodb_article_key: {diagnostics.bridge_article_key or '-'}")

        self.stdout.write("- raw article_attributes rows:")
        if not diagnostics.raw_rows:
            self.stdout.write("  - -")
        for row in diagnostics.raw_rows:
            self.stdout.write(
                f"  - supplierid={row.get('supplierid') or row.get('supplierId') or '-'} "
                f"datasupplierarticlenumber={row.get('datasupplierarticlenumber') or row.get('DataSupplierArticleNumber') or '-'} "
                f"id={row.get('id') or '-'} "
                f"displaytitle={row.get('displaytitle') or row.get('DisplayTitle') or '-'} "
                f"description={row.get('description') or row.get('Description') or '-'} "
                f"displayvalue={row.get('displayvalue') or row.get('DisplayValue') or '-'}"
            )

        self.stdout.write("- proposed attributes:")
        if not diagnostics.proposals:
            self.stdout.write("  - -")
        for row in diagnostics.proposals:
            self.stdout.write(
                f"  - attribute_name={row.get('attribute_name') or '-'} "
                f"attribute_value={row.get('attribute_value') or '-'} "
                f"autodb_attribute_id={row.get('autodb_attribute_id') or '-'}"
            )

        self.stdout.write("- current ProductAttributes:")
        if not diagnostics.current_attributes:
            self.stdout.write("  - -")
        for row in diagnostics.current_attributes:
            self.stdout.write(
                f"  - id={row.get('product_attribute_id') or '-'} "
                f"name={row.get('attribute_name') or '-'} "
                f"value={row.get('value') or '-'} "
                f"source={row.get('source') or '-'} "
                f"manual_locked={row.get('manual_locked')}"
            )

        self.stdout.write(f"- skipped_reason: {diagnostics.skipped_reason or '-'}")
        self.stdout.write("- UTR calls: 0")
