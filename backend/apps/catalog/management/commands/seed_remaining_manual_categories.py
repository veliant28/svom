from __future__ import annotations

from dataclasses import dataclass

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.models import Category
from apps.catalog.services import find_semantic_category_under_parent
from apps.catalog.services.manual_remaining_categories import REMAINING_MANUAL_CATEGORY_SPECS


@dataclass
class SeedSummary:
    parent_categories_found: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    duplicate_slugs: int = 0
    duplicate_names: int = 0
    root_categories_created: int = 0
    header_labels_before: str = ""
    header_labels_after: str = ""


class Command(BaseCommand):
    help = "Seed controlled manual child categories for remaining uncategorized products."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Preview only, do not write")

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        summary = SeedSummary()

        parent_map = self._resolve_parents()
        summary.parent_categories_found = len(parent_map)
        if len(parent_map) != len({item.root_slug for item in REMAINING_MANUAL_CATEGORY_SPECS}):
            missing = sorted({item.root_slug for item in REMAINING_MANUAL_CATEGORY_SPECS} - set(parent_map.keys()))
            raise CommandError(f"Missing parent root categories: {', '.join(missing)}")

        summary.header_labels_before = ", ".join(self._header_labels())

        if dry_run:
            self._simulate(parent_map=parent_map, summary=summary)
        else:
            with transaction.atomic():
                self._upsert(parent_map=parent_map, summary=summary)

        summary.duplicate_slugs = self._count_duplicate_slugs()
        summary.duplicate_names = self._count_duplicate_names(parent_map=parent_map)
        summary.root_categories_created = 0
        summary.header_labels_after = ", ".join(self._header_labels())

        self.stdout.write("seed_remaining_manual_categories summary:")
        self.stdout.write(f"- dry_run: {int(dry_run)}")
        self.stdout.write(f"- parent categories found: {summary.parent_categories_found}")
        self.stdout.write(f"- created: {summary.created}")
        self.stdout.write(f"- updated: {summary.updated}")
        self.stdout.write(f"- unchanged: {summary.unchanged}")
        self.stdout.write(f"- duplicate slugs: {summary.duplicate_slugs}")
        self.stdout.write(f"- duplicate names: {summary.duplicate_names}")
        self.stdout.write(f"- root categories created: {summary.root_categories_created}")
        self.stdout.write(f"- header labels before: {summary.header_labels_before}")
        self.stdout.write(f"- header labels after: {summary.header_labels_after}")
        self.stdout.write("- UTR calls=0")

    def _resolve_parents(self) -> dict[str, Category]:
        out: dict[str, Category] = {}
        needed = {item.root_slug for item in REMAINING_MANUAL_CATEGORY_SPECS}
        for category in Category.objects.filter(parent__isnull=True, slug__in=needed, source=Category.SOURCE_MANUAL):
            out[category.slug] = category
        return out

    def _simulate(self, *, parent_map: dict[str, Category], summary: SeedSummary) -> None:
        for spec in REMAINING_MANUAL_CATEGORY_SPECS:
            parent = parent_map[spec.root_slug]
            category = Category.objects.filter(slug=spec.slug).first()
            if category is None:
                category = find_semantic_category_under_parent(parent=parent, name=spec.name, include_inactive=True)
            if category is None:
                summary.created += 1
                continue
            if self._needs_update(category=category, parent_map=parent_map, spec=spec):
                summary.updated += 1
            else:
                summary.unchanged += 1

    def _upsert(self, *, parent_map: dict[str, Category], summary: SeedSummary) -> None:
        for spec in REMAINING_MANUAL_CATEGORY_SPECS:
            parent = parent_map[spec.root_slug]
            category = Category.objects.filter(slug=spec.slug).first()
            created = False
            if category is None:
                category = find_semantic_category_under_parent(parent=parent, name=spec.name, include_inactive=True)
            if category is None:
                category = Category.objects.create(
                    slug=spec.slug,
                    name=spec.name,
                    name_uk=spec.name_uk,
                    name_ru=spec.name_ru,
                    name_en=spec.name_en,
                    source=Category.SOURCE_MANUAL,
                    parent=parent,
                    show_in_header=False,
                    is_active=True,
                    sort_order=spec.sort_order,
                    source_payload={},
                    source_hash="",
                )
                created = True

            if created:
                summary.created += 1
                continue

            updates: list[str] = []
            if category.slug != spec.slug:
                category.slug = spec.slug
                updates.append("slug")
            if category.parent_id != parent.id:
                category.parent = parent
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
            if category.show_in_header:
                category.show_in_header = False
                updates.append("show_in_header")
            if not category.is_active:
                category.is_active = True
                updates.append("is_active")
            if int(category.sort_order or 0) != int(spec.sort_order):
                category.sort_order = int(spec.sort_order)
                updates.append("sort_order")

            if updates:
                category.save(update_fields=updates + ["updated_at"])
                summary.updated += 1
            else:
                summary.unchanged += 1

    def _needs_update(self, *, category: Category, parent_map: dict[str, Category], spec) -> bool:
        parent = parent_map[spec.root_slug]
        return any(
            [
                category.parent_id != parent.id,
                category.name != spec.name,
                category.name_uk != spec.name_uk,
                category.name_ru != spec.name_ru,
                category.name_en != spec.name_en,
                category.source != Category.SOURCE_MANUAL,
                bool(category.show_in_header),
                not bool(category.is_active),
                int(category.sort_order or 0) != int(spec.sort_order),
            ]
        )

    def _count_duplicate_slugs(self) -> int:
        slugs = [item.slug for item in REMAINING_MANUAL_CATEGORY_SPECS]
        return max(Category.objects.filter(slug__in=slugs).count() - len(slugs), 0)

    def _count_duplicate_names(self, *, parent_map: dict[str, Category]) -> int:
        expected_names = {" ".join(item.name.split()).casefold() for item in REMAINING_MANUAL_CATEGORY_SPECS}
        parent_ids = [item.id for item in parent_map.values()]
        counter: dict[str, int] = {}
        for name in Category.objects.filter(parent_id__in=parent_ids).values_list("name", flat=True):
            key = " ".join(str(name or "").split()).casefold()
            if key in expected_names:
                counter[key] = counter.get(key, 0) + 1
        return sum(max(count - 1, 0) for count in counter.values())

    def _header_labels(self) -> list[str]:
        return list(
            Category.objects.filter(
                parent__isnull=True,
                source=Category.SOURCE_MANUAL,
                show_in_header=True,
                is_active=True,
            )
            .order_by("sort_order", "name", "id")
            .values_list("name", flat=True)
        )
