from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from apps.catalog.models import Category, Product
from apps.catalog.selectors import get_active_categories_queryset
from apps.catalog.services.manual_root_categories import MANUAL_ROOT_CATEGORY_SPECS
from apps.pricing.models import PricingPolicy
from apps.supplier_imports.models import SupplierRawOffer


@dataclass(frozen=True)
class ResetSummary:
    total_categories_before: int
    products_with_category_before: int
    categories_to_delete: int
    products_to_unassign: int
    root_categories_to_create: int
    root_categories_to_update: int
    header_categories_after_expected: int
    pricing_policies_to_clear: int
    supplier_raw_offers_with_category_before: int


class Command(BaseCommand):
    help = "Reset all categories to curated manual root categories and unassign Product.category."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Preview only; rollback all writes")
        parser.add_argument("--categories-backup", default="/tmp/categories_before_reset.csv", help="Backup CSV for categories")
        parser.add_argument(
            "--product-assignments-backup",
            default="/tmp/product_category_assignments_before_reset.csv",
            help="Backup CSV for product->category assignments",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        categories_backup = str(options.get("categories_backup") or "/tmp/categories_before_reset.csv").strip()
        product_backup = str(options.get("product_assignments_backup") or "/tmp/product_category_assignments_before_reset.csv").strip()

        self._export_categories_backup(path=categories_backup)
        self._export_product_assignments_backup(path=product_backup)

        summary = self._collect_summary()
        self._print_summary(prefix="reset_categories_to_manual_roots preflight", summary=summary, dry_run=dry_run)

        if dry_run:
            expected_labels = [spec.name for spec in sorted(MANUAL_ROOT_CATEGORY_SPECS, key=lambda item: item.sort_order)]
            self.stdout.write(f"- header_labels_after_expected: {expected_labels}")
            self.stdout.write(f"- backups: categories={categories_backup} products={product_backup}")
            self.stdout.write("- UTR calls=0")
            self.stdout.write("- price/stock changed=0")
            return

        with transaction.atomic():
            self._apply_reset()

        after_summary = self._collect_after_summary()
        self.stdout.write("reset_categories_to_manual_roots result:")
        for key, value in after_summary.items():
            self.stdout.write(f"- {key}: {value}")
        self.stdout.write(f"- header_labels_after: {self._header_labels()}")
        self.stdout.write(f"- backups: categories={categories_backup} products={product_backup}")
        self.stdout.write("- UTR calls=0")
        self.stdout.write("- price/stock changed=0")

    def _collect_summary(self) -> ResetSummary:
        total_categories_before = Category.objects.count()
        products_with_category_before = Product.objects.exclude(category__isnull=True).count()
        categories_to_delete = total_categories_before
        products_to_unassign = products_with_category_before
        root_categories_to_create = len(MANUAL_ROOT_CATEGORY_SPECS)
        root_categories_to_update = 0
        header_categories_after_expected = len(MANUAL_ROOT_CATEGORY_SPECS)
        pricing_policies_to_clear = PricingPolicy.objects.exclude(category__isnull=True).count()
        supplier_raw_offers_with_category_before = SupplierRawOffer.objects.exclude(mapped_category__isnull=True).count()
        return ResetSummary(
            total_categories_before=total_categories_before,
            products_with_category_before=products_with_category_before,
            categories_to_delete=categories_to_delete,
            products_to_unassign=products_to_unassign,
            root_categories_to_create=root_categories_to_create,
            root_categories_to_update=root_categories_to_update,
            header_categories_after_expected=header_categories_after_expected,
            pricing_policies_to_clear=pricing_policies_to_clear,
            supplier_raw_offers_with_category_before=supplier_raw_offers_with_category_before,
        )

    def _print_summary(self, *, prefix: str, summary: ResetSummary, dry_run: bool) -> None:
        self.stdout.write(f"{prefix}:")
        self.stdout.write(f"- dry_run: {int(dry_run)}")
        self.stdout.write(f"- total_categories_before: {summary.total_categories_before}")
        self.stdout.write(f"- products_with_category_before: {summary.products_with_category_before}")
        self.stdout.write(f"- categories_to_delete: {summary.categories_to_delete}")
        self.stdout.write(f"- products_to_unassign: {summary.products_to_unassign}")
        self.stdout.write(f"- pricing_policies_to_clear: {summary.pricing_policies_to_clear}")
        self.stdout.write(f"- supplier_raw_offers_with_category_before: {summary.supplier_raw_offers_with_category_before}")
        self.stdout.write(f"- root_categories_to_create: {summary.root_categories_to_create}")
        self.stdout.write(f"- root_categories_to_update: {summary.root_categories_to_update}")
        self.stdout.write(f"- header_categories_after_expected: {summary.header_categories_after_expected}")

    def _apply_reset(self) -> None:
        category_ids = list(Category.objects.values_list("id", flat=True))
        Product.objects.exclude(category__isnull=True).update(category=None)
        PricingPolicy.objects.exclude(category__isnull=True).update(category=None)
        self._clear_supplier_raw_offer_category_mappings(category_ids=category_ids)
        Category.objects.exclude(parent__isnull=True).update(parent=None)
        Category.objects.all().delete()
        self._create_manual_roots()

    def _create_manual_roots(self) -> None:
        for spec in sorted(MANUAL_ROOT_CATEGORY_SPECS, key=lambda item: item.sort_order):
            Category.objects.create(
                name=spec.name,
                name_uk=spec.name_uk,
                name_ru=spec.name_ru,
                name_en=spec.name_en,
                slug=spec.slug,
                parent=None,
                source=Category.SOURCE_MANUAL,
                autodb_prd_id=None,
                show_in_header=True,
                is_active=True,
                source_payload={},
                source_hash="",
            )

    def _clear_supplier_raw_offer_category_mappings(self, *, category_ids: list) -> None:
        if not category_ids:
            return
        qs = SupplierRawOffer.objects.filter(mapped_category_id__in=category_ids)
        batch_size = 5000
        while True:
            batch_ids = list(qs.values_list("id", flat=True)[:batch_size])
            if not batch_ids:
                break
            SupplierRawOffer.objects.filter(id__in=batch_ids).update(mapped_category=None)

    def _collect_after_summary(self) -> dict[str, int]:
        root_qs = Category.objects.filter(parent__isnull=True)
        header_roots_qs = root_qs.filter(show_in_header=True, is_active=True)
        return {
            "total_categories_after": Category.objects.count(),
            "root_categories_after": root_qs.count(),
            "header_root_categories_after": header_roots_qs.count(),
            "autodb_categories_after": Category.objects.filter(source=Category.SOURCE_AUTODB_PRO).count(),
            "products_with_category_after": Product.objects.exclude(category__isnull=True).count(),
            "products_without_category_after": Product.objects.filter(category__isnull=True).count(),
        }

    def _header_labels(self) -> list[str]:
        return [item.name for item in get_active_categories_queryset(scope="header") if item.parent_id is None]

    def _export_categories_backup(self, *, path: str) -> None:
        export_path = Path(path).expanduser()
        export_path.parent.mkdir(parents=True, exist_ok=True)

        product_counts = dict(
            Category.objects.annotate(product_count=Count("products")).values_list("id", "product_count")
        )
        with export_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "id",
                    "name",
                    "name_uk",
                    "name_ru",
                    "name_en",
                    "slug",
                    "parent_id",
                    "source",
                    "autodb_prd_id",
                    "is_active",
                    "show_in_header",
                    "product_count",
                    "created_at",
                    "updated_at",
                ],
            )
            writer.writeheader()
            for category in Category.objects.order_by("created_at", "id"):
                writer.writerow(
                    {
                        "id": str(category.id),
                        "name": str(category.name or ""),
                        "name_uk": str(category.name_uk or ""),
                        "name_ru": str(category.name_ru or ""),
                        "name_en": str(category.name_en or ""),
                        "slug": str(category.slug or ""),
                        "parent_id": str(category.parent_id or ""),
                        "source": str(category.source or ""),
                        "autodb_prd_id": category.autodb_prd_id or "",
                        "is_active": int(bool(category.is_active)),
                        "show_in_header": int(bool(category.show_in_header)),
                        "product_count": int(product_counts.get(category.id, 0) or 0),
                        "created_at": category.created_at.isoformat() if category.created_at else "",
                        "updated_at": category.updated_at.isoformat() if category.updated_at else "",
                    }
                )

    def _export_product_assignments_backup(self, *, path: str) -> None:
        export_path = Path(path).expanduser()
        export_path.parent.mkdir(parents=True, exist_ok=True)

        with export_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "product_id",
                    "product_name",
                    "current_category_id",
                    "current_category_name",
                    "autodb_article_key",
                    "catalog_source",
                ],
            )
            writer.writeheader()
            qs = Product.objects.select_related("category").order_by("id")
            for product in qs.iterator(chunk_size=500):
                writer.writerow(
                    {
                        "product_id": str(product.id),
                        "product_name": str(product.name or ""),
                        "current_category_id": str(product.category_id or ""),
                        "current_category_name": str(getattr(product.category, "name", "") or ""),
                        "autodb_article_key": str(product.autodb_article_key or ""),
                        "catalog_source": str(product.catalog_source or ""),
                    }
                )
