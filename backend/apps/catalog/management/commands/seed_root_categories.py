from __future__ import annotations

from dataclasses import dataclass

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.models import Category
from apps.catalog.services.manual_root_categories import MANUAL_ROOT_CATEGORY_SPECS


@dataclass
class SeedSummary:
    total_before: int = 0
    roots_before: int = 0
    nav_roots_before: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    nav_hidden_other_roots: int = 0
    total_after: int = 0
    roots_after: int = 0
    nav_roots_after: int = 0
    manual_roots_after: int = 0
    autodb_roots_after: int = 0


class Command(BaseCommand):
    help = "Create/update curated root categories for storefront header navigation."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Preview changes without DB writes.")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force-hide header visibility for root categories outside curated list.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        force = bool(options.get("force"))
        summary = SeedSummary()
        summary.total_before = Category.objects.count()
        summary.roots_before = Category.objects.filter(parent__isnull=True).count()
        summary.nav_roots_before = Category.objects.filter(parent__isnull=True, is_active=True, show_in_header=True).count()

        if dry_run:
            self._simulate(summary=summary, force=force)
            self._print(summary=summary, dry_run=dry_run, force=force, simulated=True)
            return

        with transaction.atomic():
            self._upsert_roots(summary=summary)
            if force:
                summary.nav_hidden_other_roots = self._hide_non_curated_root_nav()

        summary.total_after = Category.objects.count()
        summary.roots_after = Category.objects.filter(parent__isnull=True).count()
        summary.nav_roots_after = Category.objects.filter(parent__isnull=True, is_active=True, show_in_header=True).count()
        summary.manual_roots_after = Category.objects.filter(parent__isnull=True, source=Category.SOURCE_MANUAL).count()
        summary.autodb_roots_after = Category.objects.filter(parent__isnull=True, source=Category.SOURCE_AUTODB_PRO).count()
        self._print(summary=summary, dry_run=dry_run, force=force, simulated=False)

    def _upsert_roots(self, *, summary: SeedSummary) -> None:
        curated_slugs = {item.slug for item in MANUAL_ROOT_CATEGORY_SPECS}
        for spec in MANUAL_ROOT_CATEGORY_SPECS:
            category, created = Category.objects.get_or_create(
                slug=spec.slug,
                defaults={
                    "name": spec.name,
                    "name_uk": spec.name_uk,
                    "name_ru": spec.name_ru,
                    "name_en": spec.name_en,
                    "parent": None,
                    "source": Category.SOURCE_MANUAL,
                    "autodb_prd_id": None,
                    "show_in_header": True,
                    "is_active": True,
                    "sort_order": spec.sort_order,
                    "source_payload": {},
                    "source_hash": "",
                },
            )
            if created:
                summary.created += 1
                continue

            updates: list[str] = []
            if category.parent_id is not None:
                category.parent = None
                updates.append("parent")
            if category.name != spec.name:
                category.name = spec.name
                updates.append("name")
            if category.name_uk != spec.name_uk:
                category.name_uk = spec.name_uk
                updates.append("name_uk")
            if category.name_ru != spec.name_ru:
                category.name_ru = spec.name_ru
                updates.append("name_ru")
            if category.name_en != spec.name_en:
                category.name_en = spec.name_en
                updates.append("name_en")
            if category.source != Category.SOURCE_MANUAL:
                category.source = Category.SOURCE_MANUAL
                updates.append("source")
            if category.autodb_prd_id is not None:
                category.autodb_prd_id = None
                updates.append("autodb_prd_id")
            if not category.is_active:
                category.is_active = True
                updates.append("is_active")
            if not category.show_in_header:
                category.show_in_header = True
                updates.append("show_in_header")
            if int(category.sort_order or 0) != int(spec.sort_order):
                category.sort_order = int(spec.sort_order)
                updates.append("sort_order")
            if updates:
                category.save(update_fields=updates + ["updated_at"])
                summary.updated += 1
            else:
                summary.unchanged += 1

        # If non-curated categories accidentally use curated slugs via stale data, surface warning.
        collisions = Category.objects.filter(slug__in=curated_slugs).exclude(parent__isnull=True)
        if collisions.exists():
            self.stdout.write(self.style.WARNING(f"warning: found non-root categories with curated slugs: {collisions.count()}"))

    def _simulate(self, *, summary: SeedSummary, force: bool) -> None:
        curated_slugs = {item.slug for item in MANUAL_ROOT_CATEGORY_SPECS}
        for spec in MANUAL_ROOT_CATEGORY_SPECS:
            category = Category.objects.filter(slug=spec.slug).first()
            if category is None:
                summary.created += 1
                continue
            changed = (
                category.parent_id is not None
                or category.name != spec.name
                or category.name_uk != spec.name_uk
                or category.name_ru != spec.name_ru
                or category.name_en != spec.name_en
                or category.source != Category.SOURCE_MANUAL
                or category.autodb_prd_id is not None
                or not category.is_active
                or not category.show_in_header
                or int(category.sort_order or 0) != int(spec.sort_order)
            )
            if changed:
                summary.updated += 1
            else:
                summary.unchanged += 1
        if force:
            summary.nav_hidden_other_roots = Category.objects.filter(parent__isnull=True, show_in_header=True).exclude(slug__in=curated_slugs).count()

    def _hide_non_curated_root_nav(self) -> int:
        curated_slugs = [item.slug for item in MANUAL_ROOT_CATEGORY_SPECS]
        qs = Category.objects.filter(parent__isnull=True).exclude(slug__in=curated_slugs).filter(show_in_header=True)
        count = qs.count()
        if count:
            qs.update(show_in_header=False)
        return count

    def _print(self, *, summary: SeedSummary, dry_run: bool, force: bool, simulated: bool) -> None:
        header_labels = [item.name for item in MANUAL_ROOT_CATEGORY_SPECS] if simulated else [
            item.name
            for item in Category.objects.filter(parent__isnull=True, show_in_header=True, is_active=True, source=Category.SOURCE_MANUAL)
            .order_by("sort_order", "name", "id")
        ]
        self.stdout.write("seed_root_categories summary:")
        self.stdout.write(f"- dry_run: {int(dry_run)}")
        self.stdout.write(f"- force: {int(force)}")
        self.stdout.write(f"- total_before: {summary.total_before}")
        self.stdout.write(f"- roots_before: {summary.roots_before}")
        self.stdout.write(f"- nav_roots_before: {summary.nav_roots_before}")
        self.stdout.write(f"- created: {summary.created}")
        self.stdout.write(f"- updated: {summary.updated}")
        self.stdout.write(f"- unchanged: {summary.unchanged}")
        self.stdout.write(f"- nav_hidden_other_roots: {summary.nav_hidden_other_roots}")
        if simulated:
            self.stdout.write(f"- expected_header_labels: {header_labels}")
            self.stdout.write("- simulated_only: 1")
        else:
            self.stdout.write(f"- total_after: {summary.total_after}")
            self.stdout.write(f"- roots_after: {summary.roots_after}")
            self.stdout.write(f"- nav_roots_after: {summary.nav_roots_after}")
            self.stdout.write(f"- manual_roots_after: {summary.manual_roots_after}")
            self.stdout.write(f"- autodb_roots_after: {summary.autodb_roots_after}")
            self.stdout.write(f"- header_labels_after: {header_labels}")
        self.stdout.write("- UTR calls=0")
        self.stdout.write("- product/offer import runs=0")
