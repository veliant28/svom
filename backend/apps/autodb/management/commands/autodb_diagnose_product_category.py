from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services.product_category_enrichment import AutoDbProductCategoryEnrichmentService
from apps.catalog.models import Product


class Command(BaseCommand):
    help = "Diagnose Product category enrichment from local Auto_DB_Pro rows."

    def add_arguments(self, parser):
        parser.add_argument("--product-id", required=True, help="Product UUID")

    def handle(self, *args, **options):
        product_id = str(options.get("product_id") or "").strip()
        if not product_id:
            raise CommandError("--product-id is required")

        try:
            product = Product.objects.select_related("brand", "category", "category__parent").get(pk=product_id)
        except Product.DoesNotExist as exc:
            raise CommandError(f"Product not found: {product_id}") from exc

        service = AutoDbProductCategoryEnrichmentService()
        diagnostics = service.build_diagnostics(product=product)

        self.stdout.write("Auto_DB_Pro product category diagnostics:")
        self.stdout.write(f"- product_id: {product.id}")
        self.stdout.write(f"- product_name: {product.name or '-'}")
        self.stdout.write(f"- current_category: {diagnostics.current_category_name or '-'} ({diagnostics.current_category_id or '-'})")
        self.stdout.write(f"- current_category_source: {diagnostics.current_category_source or '-'}")
        self.stdout.write(f"- current_category_autodb_prd_id: {diagnostics.current_category_autodb_prd_id or '-'}")
        self.stdout.write(f"- bridge.autodb_supplier_id: {diagnostics.bridge_supplier_id or '-'}")
        self.stdout.write(f"- bridge.autodb_article_number: {diagnostics.bridge_article_number or '-'}")
        self.stdout.write(f"- bridge.autodb_article_key: {diagnostics.bridge_article_key or '-'}")

        self.stdout.write("- article_prd rows:")
        if not diagnostics.article_prd_rows:
            self.stdout.write("  - -")
        for row in diagnostics.article_prd_rows:
            self.stdout.write(
                f"  - supplierid={row.get('supplierid') or row.get('supplierId') or '-'} "
                f"datasupplierarticlenumber={row.get('datasupplierarticlenumber') or row.get('DataSupplierArticleNumber') or '-'} "
                f"productid={row.get('productid') or row.get('productId') or row.get('ProductId') or '-'}"
            )

        self.stdout.write("- articles row:")
        if not diagnostics.article_row:
            self.stdout.write("  - -")
        else:
            self.stdout.write(
                f"  - supplierid={diagnostics.article_row.get('supplierid') or diagnostics.article_row.get('supplierId') or '-'} "
                f"datasupplierarticlenumber={diagnostics.article_row.get('datasupplierarticlenumber') or diagnostics.article_row.get('DataSupplierArticleNumber') or '-'} "
                f"NormalizedDescription={diagnostics.article_row.get('NormalizedDescription') or diagnostics.article_row.get('normalizeddescription') or '-'} "
                f"Description={diagnostics.article_row.get('Description') or diagnostics.article_row.get('description') or '-'}"
            )

        self.stdout.write("- article_links rows:")
        if not diagnostics.article_links_rows:
            self.stdout.write("  - -")
        for row in diagnostics.article_links_rows:
            self.stdout.write(
                f"  - supplierid={row.get('supplierid') or row.get('supplierId') or '-'} "
                f"datasupplierarticlenumber={row.get('datasupplierarticlenumber') or row.get('DataSupplierArticleNumber') or '-'} "
                f"productid={row.get('productid') or row.get('productId') or row.get('ProductId') or '-'}"
            )

        self.stdout.write("- prd candidates:")
        if not diagnostics.prd_rows:
            self.stdout.write("  - -")
        for row in diagnostics.prd_rows:
            self.stdout.write(
                f"  - id={row.get('id') or row.get('productid') or row.get('productId') or '-'} "
                f"parentid={row.get('parentid') or row.get('parentId') or '-'} "
                f"description={row.get('description') or '-'} "
                f"fulldescription={row.get('fulldescription') or row.get('fullDescription') or '-'}"
            )

        self.stdout.write(f"- chosen_prd_id: {diagnostics.chosen_prd_id or '-'}")
        self.stdout.write(f"- chosen_source: {diagnostics.chosen_source or '-'}")
        self.stdout.write(f"- chosen_prd_row: {diagnostics.chosen_prd_row or '-'}")
        self.stdout.write(f"- autodb_article_title: {diagnostics.autodb_article_title or '-'}")
        self.stdout.write(f"- autodb_prd_title: {diagnostics.autodb_prd_title or '-'}")
        self.stdout.write(f"- suspicious_link: {diagnostics.suspicious_link}")
        self.stdout.write(f"- suspicious_reason: {diagnostics.suspicious_reason or '-'}")
        self.stdout.write(f"- proposed_category: {diagnostics.proposed_category_name or '-'} ({diagnostics.proposed_category_id or '-'})")
        self.stdout.write(f"- proposed_category_source: {diagnostics.proposed_category_source or '-'}")
        self.stdout.write(f"- proposed_category_autodb_prd_id: {diagnostics.proposed_category_autodb_prd_id or '-'}")
        self.stdout.write(f"- skipped_reason: {diagnostics.skipped_reason or '-'}")
        self.stdout.write("- UTR calls: 0")
