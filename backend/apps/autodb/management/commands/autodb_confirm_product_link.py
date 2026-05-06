from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services.fitment_quality import AutoDbProductLinkQualityService
from apps.catalog.models import Product


class Command(BaseCommand):
    help = "Manually confirm or block Auto_DB_Pro product link quality without deleting fitments."

    def add_arguments(self, parser):
        parser.add_argument("--product-id", required=True, type=str, help="Product UUID.")
        parser.add_argument(
            "--status",
            required=True,
            choices=("trusted", "suspicious", "needs_manual_review"),
            help="Manual link quality status.",
        )
        parser.add_argument("--reason", type=str, default="", help="Machine-friendly reason, e.g. suspicious_link.")
        parser.add_argument("--autodb-title", type=str, default="", help="Optional Auto_DB_Pro article title for evidence.")
        parser.add_argument("--note", type=str, default="", help="Optional operator note.")

    def handle(self, *args, **options):
        product_id = str(options.get("product_id") or "").strip()
        status = str(options.get("status") or "").strip()
        reason = str(options.get("reason") or "").strip()
        autodb_title = str(options.get("autodb_title") or "").strip()
        note = str(options.get("note") or "").strip()

        product = Product.objects.filter(pk=product_id).first()
        if product is None:
            raise CommandError(f"Product not found: {product_id}")

        service = AutoDbProductLinkQualityService()
        try:
            result = service.confirm_manual_status(
                product=product,
                status=status,
                reason=reason,
                note=note,
                evidence={
                    "source": "manual_confirmation",
                    "product_name": str(product.name or ""),
                    "autodb_article_key": str(product.autodb_article_key or ""),
                    "autodb_title": autodb_title,
                    "reason": reason,
                    "note": note,
                },
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write("Auto_DB_Pro product link quality saved:")
        self.stdout.write(f"- product_id: {product.id}")
        self.stdout.write(f"- product: {product.name}")
        self.stdout.write(f"- autodb_article_key: {product.autodb_article_key or '-'}")
        self.stdout.write(f"- status: {result.status or '-'}")
        self.stdout.write(f"- manually_confirmed: {result.manually_confirmed}")
        self.stdout.write(f"- excluded_from_public_filtering: {result.excluded_from_public_filtering}")
        self.stdout.write(f"- reason: {result.reason or '-'}")
