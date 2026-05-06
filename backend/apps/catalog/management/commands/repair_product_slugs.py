from __future__ import annotations

from dataclasses import dataclass

from django.core.management.base import BaseCommand
from django.db.models import QuerySet

from apps.catalog.models import Product
from apps.catalog.services import (
    generate_unique_product_slug,
    get_product_display_name,
    is_code_like_product_name,
)


@dataclass
class SlugRepairSummary:
    processed: int = 0
    updated: int = 0
    skipped_already_good: int = 0
    skipped_needs_explicit_rewrite: int = 0
    skipped_manual_locked: int = 0


class Command(BaseCommand):
    help = "Safely repair product slugs using localized display names. Existing code-like slugs require --rewrite-existing."

    def add_arguments(self, parser):
        parser.add_argument("--product-id", type=str, default="", help="Process one Product UUID")
        parser.add_argument("--limit", type=int, default=100, help="Maximum products to inspect")
        parser.add_argument("--dry-run", action="store_true", help="Preview only, no writes")
        parser.add_argument(
            "--rewrite-existing",
            action="store_true",
            help="Allow rewriting existing code-like slugs (may change URLs).",
        )

    def handle(self, *args, **options):
        product_id = str(options.get("product_id") or "").strip()
        limit = max(int(options.get("limit") or 100), 1)
        dry_run = bool(options.get("dry_run"))
        rewrite_existing = bool(options.get("rewrite_existing"))

        queryset = self._build_queryset(product_id=product_id)[:limit]
        summary = SlugRepairSummary()

        self.stdout.write(
            "repair_product_slugs started "
            f"dry_run={dry_run} rewrite_existing={rewrite_existing} limit={limit} product_id={product_id or '-'}"
        )

        for product in queryset.iterator(chunk_size=100):
            summary.processed += 1
            current_slug = str(product.slug or "").strip()
            current_is_code_like = is_code_like_product_name(current_slug)
            display_name = get_product_display_name(product, "uk")
            preferred = f"{display_name} {product.brand.name if product.brand_id else ''} {product.article or product.autodb_article_number or ''}"
            new_slug = generate_unique_product_slug(
                name=preferred.strip() or display_name or product.name or "product",
                preferred_slug="",
                exclude_product_id=str(product.id),
            )

            should_repair_missing = not current_slug
            should_repair_code_like = bool(current_slug) and current_is_code_like and current_slug != new_slug

            if bool(product.name_manually_locked):
                summary.skipped_manual_locked += 1
                self.stdout.write(f"- product={product.id} status=skipped_manual_locked slug={current_slug or '-'}")
                continue

            if should_repair_missing or (rewrite_existing and should_repair_code_like):
                if not dry_run:
                    product.slug = new_slug
                    product.save(update_fields=["slug", "updated_at"])
                summary.updated += 1
                self.stdout.write(
                    f"- product={product.id} status={'updated' if not dry_run else 'dry_run_update'} "
                    f"old_slug={current_slug or '-'} new_slug={new_slug}"
                )
                continue

            if should_repair_code_like and not rewrite_existing:
                summary.skipped_needs_explicit_rewrite += 1
                self.stdout.write(
                    f"- product={product.id} status=skipped_needs_explicit_rewrite "
                    f"old_slug={current_slug or '-'} proposed_slug={new_slug}"
                )
                continue

            summary.skipped_already_good += 1
            self.stdout.write(f"- product={product.id} status=skipped_already_good slug={current_slug or '-'}")

        self.stdout.write("repair_product_slugs summary:")
        self.stdout.write(f"- processed: {summary.processed}")
        self.stdout.write(f"- updated: {summary.updated}")
        self.stdout.write(f"- skipped_already_good: {summary.skipped_already_good}")
        self.stdout.write(f"- skipped_needs_explicit_rewrite: {summary.skipped_needs_explicit_rewrite}")
        self.stdout.write(f"- skipped_manual_locked: {summary.skipped_manual_locked}")
        self.stdout.write("- note: no slug aliases/redirects are created by this command.")
        self.stdout.write("- UTR calls: 0")

    def _build_queryset(self, *, product_id: str) -> QuerySet[Product]:
        qs = Product.objects.select_related("brand").order_by("id")
        if product_id:
            qs = qs.filter(id=product_id)
        return qs

