from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services.product_linker import AutoDbProductLinkService


class Command(BaseCommand):
    help = "Link Product for one SupplierRawOffer using Auto_DB_Pro article lookup."

    def add_arguments(self, parser):
        parser.add_argument("--raw-offer-id", required=True, help="SupplierRawOffer UUID")

    def handle(self, *args, **options):
        raw_offer_id = str(options.get("raw_offer_id") or "").strip()
        if not raw_offer_id:
            raise CommandError("--raw-offer-id is required")

        service = AutoDbProductLinkService()
        try:
            result = service.link_from_raw_offer(raw_offer_id=raw_offer_id)
        except Exception as exc:  # noqa: BLE001
            raise CommandError(str(exc)) from exc

        self.stdout.write("Auto_DB_Pro raw offer link:")
        self.stdout.write(f"- product_id: {result.product_id}")
        self.stdout.write(f"- linked: {result.linked}")
        self.stdout.write(f"- autodb_supplier_id: {result.supplier_id or '-'}")
        self.stdout.write(f"- autodb_article_id: {result.article_id or '-'}")
        self.stdout.write(f"- autodb_article_number: {result.article_number or '-'}")
        self.stdout.write(f"- autodb_article_key: {result.article_key or '-'}")
        self.stdout.write(f"- normalized_brand: {result.normalized_brand}")
        self.stdout.write(f"- normalized_article: {result.normalized_article}")
        if result.warnings:
            self.stdout.write("- warnings:")
            for warning in result.warnings:
                self.stdout.write(f"  - {warning}")
