from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.autodb.services.product_name_translation import ProductNameTranslationService
from apps.catalog.models import Product
from apps.catalog.services.product_management import sanitize_product_name


@dataclass
class TranslateSummary:
    processed: int = 0
    translated: int = 0
    pending: int = 0
    failed: int = 0
    skipped_manual_locked: int = 0
    skipped_no_source_text: int = 0
    skipped_hash_unchanged: int = 0


class Command(BaseCommand):
    help = "Translate Product names (uk/ru/en) from Product.name_source_text for pending/failed records."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="Limit products count")
        parser.add_argument("--dry-run", action="store_true", help="Show changes without saving")
        parser.add_argument("--only-pending", action="store_true", help="Process only pending/failed translation statuses")
        parser.add_argument("--product-id", type=str, default="", help="Process one Product UUID")

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        only_pending = bool(options.get("only_pending"))
        product_id = str(options.get("product_id") or "").strip()
        limit = max(int(options.get("limit") or 0), 0)
        translator = ProductNameTranslationService()

        qs = Product.objects.order_by("id")
        if product_id:
            qs = qs.filter(pk=product_id)
        if only_pending:
            qs = qs.filter(
                Q(name_translation_status__in=["", Product.NAME_TRANSLATION_PENDING, Product.NAME_TRANSLATION_FAILED])
                | Q(name_uk="")
                | Q(name_ru="")
                | Q(name_en="")
            )
        if limit > 0:
            qs = qs[:limit]

        summary = TranslateSummary()
        self.stdout.write(f"Auto_DB_Pro product translation started dry_run={dry_run} only_pending={only_pending}")
        for product in qs.iterator(chunk_size=200):
            summary.processed += 1
            status, translation_status = self._process_product(product=product, translator=translator, dry_run=dry_run)
            if status == "skipped_manual_locked":
                summary.skipped_manual_locked += 1
            elif status == "skipped_no_source_text":
                summary.skipped_no_source_text += 1
            elif status == "skipped_hash_unchanged":
                summary.skipped_hash_unchanged += 1

            if translation_status == Product.NAME_TRANSLATION_TRANSLATED:
                summary.translated += 1
            elif translation_status == Product.NAME_TRANSLATION_FAILED:
                summary.failed += 1
            elif translation_status == Product.NAME_TRANSLATION_PENDING:
                summary.pending += 1

        self.stdout.write("Auto_DB_Pro product translation summary:")
        self.stdout.write(f"- processed: {summary.processed}")
        self.stdout.write(f"- translated: {summary.translated}")
        self.stdout.write(f"- pending: {summary.pending}")
        self.stdout.write(f"- failed: {summary.failed}")
        self.stdout.write(f"- skipped_manual_locked: {summary.skipped_manual_locked}")
        self.stdout.write(f"- skipped_no_source_text: {summary.skipped_no_source_text}")
        self.stdout.write(f"- skipped_hash_unchanged: {summary.skipped_hash_unchanged}")
        self.stdout.write("- UTR calls: 0")

    def _process_product(
        self,
        *,
        product: Product,
        translator: ProductNameTranslationService,
        dry_run: bool,
    ) -> tuple[str, str]:
        if bool(product.name_manually_locked):
            self.stdout.write(f"- product_id={product.id} status=skipped_manual_locked")
            return "skipped_manual_locked", Product.NAME_TRANSLATION_MANUAL_LOCKED

        source_text = sanitize_product_name(str(product.name_source_text or ""))
        if not source_text:
            self.stdout.write(f"- product_id={product.id} status=skipped_no_source_text")
            return "skipped_no_source_text", str(product.name_translation_status or "")

        source_kind = str(product.name_source or Product.NAME_SOURCE_AUTODB_PRO)
        source_hash = sha1(f"{source_kind}:{source_text}".encode("utf-8")).hexdigest()  # noqa: S324
        if (
            str(product.name_source_hash or "") == source_hash
            and str(product.name_translation_status or "") == Product.NAME_TRANSLATION_TRANSLATED
            and str(product.name_uk or "").strip()
            and str(product.name_ru or "").strip()
            and str(product.name_en or "").strip()
        ):
            self.stdout.write(f"- product_id={product.id} status=skipped_hash_unchanged")
            return "skipped_hash_unchanged", Product.NAME_TRANSLATION_TRANSLATED

        translated = translator.translate_product_name(source_text=source_text)
        name_uk = translated.uk or source_text
        name_ru = translated.ru or source_text
        name_en = translated.en or source_text

        if not dry_run:
            product.name = name_uk
            product.name_uk = name_uk
            product.name_ru = name_ru
            product.name_en = name_en
            product.name_source_hash = source_hash
            product.name_translation_status = translated.status
            product.name_translation_error = translated.error
            product.save(
                update_fields=(
                    "name",
                    "name_uk",
                    "name_ru",
                    "name_en",
                    "name_source_hash",
                    "name_translation_status",
                    "name_translation_error",
                    "updated_at",
                )
            )

        self.stdout.write(
            f"- product_id={product.id} status=updated source_text={source_text} "
            f"name_uk={name_uk} name_ru={name_ru} name_en={name_en} "
            f"translation_status={translated.status} error={translated.error or '-'}"
        )
        return "updated", translated.status
