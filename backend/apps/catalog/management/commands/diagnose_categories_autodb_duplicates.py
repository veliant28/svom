from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.catalog.models import Category


def _normalize_name(value: str) -> str:
    return " ".join(str(value or "").split()).casefold()


@dataclass(frozen=True)
class DuplicateEntry:
    group_type: str
    group_key: str
    category: Category
    product_count: int


class Command(BaseCommand):
    help = "Diagnose duplicate Auto_DB_Pro categories and header visibility state."

    def add_arguments(self, parser):
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV export path")

    def handle(self, *args, **options):
        export_csv = str(options.get("export_csv") or "").strip()

        categories = list(Category.objects.select_related("parent").order_by("created_at", "id"))
        product_counts = dict(
            Category.objects.annotate(product_count=Count("products")).values_list("id", "product_count")
        )

        total_count = len(categories)
        source_counts = Counter((item.source or "").strip() or "empty" for item in categories)
        root_counts = Counter((item.source or "").strip() or "empty" for item in categories if item.parent_id is None)
        active_counts = Counter((item.source or "").strip() or "empty" for item in categories if item.is_active)
        nav_counts = Counter(
            (item.source or "").strip() or "empty"
            for item in categories
            if item.show_in_header and item.is_active and item.parent_id is None
        )

        duplicates: list[DuplicateEntry] = []
        duplicates.extend(self._collect_autodb_prd_duplicates(categories, product_counts))
        duplicates.extend(self._collect_normalized_name_duplicates(categories, product_counts, with_source=False))
        duplicates.extend(self._collect_normalized_name_duplicates(categories, product_counts, with_source=True))
        duplicates.extend(self._collect_slug_duplicates(categories, product_counts))

        self.stdout.write("Category diagnostics:")
        self.stdout.write(f"- total_count: {total_count}")
        self.stdout.write("- count_by_source:")
        for source, count in sorted(source_counts.items()):
            self.stdout.write(f"  - {source}: {count}")
        self.stdout.write(f"- autodb_pro_count: {source_counts.get(Category.SOURCE_AUTODB_PRO, 0)}")
        self.stdout.write(f"- manual_count: {source_counts.get(Category.SOURCE_MANUAL, 0)}")
        self.stdout.write(f"- import_count: {source_counts.get(Category.SOURCE_IMPORT, 0)}")
        self.stdout.write(f"- empty_source_count: {source_counts.get('empty', 0)}")

        self.stdout.write("- root_categories_by_source:")
        for source, count in sorted(root_counts.items()):
            self.stdout.write(f"  - {source}: {count}")

        self.stdout.write("- active_categories_by_source:")
        for source, count in sorted(active_counts.items()):
            self.stdout.write(f"  - {source}: {count}")

        self.stdout.write("- header_navigation_categories_by_source:")
        for source, count in sorted(nav_counts.items()):
            self.stdout.write(f"  - {source}: {count}")
        self.stdout.write(f"- header_navigation_total_roots: {sum(nav_counts.values())}")

        grouped_counts = Counter(item.group_type for item in duplicates)
        self.stdout.write("- duplicates:")
        self.stdout.write(f"  - autodb_prd_id_groups: {grouped_counts.get('autodb_prd_id', 0)}")
        self.stdout.write(f"  - normalized_name_groups: {grouped_counts.get('normalized_name', 0)}")
        self.stdout.write(f"  - normalized_name_source_groups: {grouped_counts.get('normalized_name_source', 0)}")
        self.stdout.write(f"  - slug_groups: {grouped_counts.get('slug', 0)}")

        for entry in duplicates[:60]:
            category = entry.category
            self.stdout.write(
                f"- dup[{entry.group_type}] key={entry.group_key} "
                f"name={category.name or '-'} source={category.source or '-'} autodb_prd_id={category.autodb_prd_id or '-'} "
                f"parent_id={category.parent_id or '-'} slug={category.slug or '-'} products={entry.product_count} "
                f"is_active={int(bool(category.is_active))} show_in_header={int(bool(category.show_in_header))} "
                f"created_at={category.created_at} updated_at={category.updated_at}"
            )

        if export_csv:
            self._export_csv(export_csv=export_csv, rows=duplicates)
            self.stdout.write(f"- csv_export: {export_csv}")

        self.stdout.write("- deleted: 0")
        self.stdout.write("- UTR calls: 0")

    def _collect_autodb_prd_duplicates(
        self,
        categories: list[Category],
        product_counts: dict,
    ) -> list[DuplicateEntry]:
        groups: dict[int, list[Category]] = defaultdict(list)
        for category in categories:
            if category.autodb_prd_id is None:
                continue
            groups[int(category.autodb_prd_id)].append(category)

        out: list[DuplicateEntry] = []
        for key, items in groups.items():
            if len(items) <= 1:
                continue
            for category in items:
                out.append(
                    DuplicateEntry(
                        group_type="autodb_prd_id",
                        group_key=str(key),
                        category=category,
                        product_count=int(product_counts.get(category.id, 0) or 0),
                    )
                )
        return out

    def _collect_normalized_name_duplicates(
        self,
        categories: list[Category],
        product_counts: dict,
        *,
        with_source: bool,
    ) -> list[DuplicateEntry]:
        groups: dict[tuple[str, str], list[Category]] = defaultdict(list)
        for category in categories:
            normalized = _normalize_name(category.name)
            if not normalized:
                continue
            source = (category.source or "").strip() if with_source else "*"
            groups[(source, normalized)].append(category)

        out: list[DuplicateEntry] = []
        group_type = "normalized_name_source" if with_source else "normalized_name"
        for (source, normalized), items in groups.items():
            if len(items) <= 1:
                continue
            key = f"{source}:{normalized}" if with_source else normalized
            for category in items:
                out.append(
                    DuplicateEntry(
                        group_type=group_type,
                        group_key=key,
                        category=category,
                        product_count=int(product_counts.get(category.id, 0) or 0),
                    )
                )
        return out

    def _collect_slug_duplicates(self, categories: list[Category], product_counts: dict) -> list[DuplicateEntry]:
        groups: dict[str, list[Category]] = defaultdict(list)
        for category in categories:
            slug = str(category.slug or "").strip()
            if not slug:
                continue
            groups[slug].append(category)

        out: list[DuplicateEntry] = []
        for slug, items in groups.items():
            if len(items) <= 1:
                continue
            for category in items:
                out.append(
                    DuplicateEntry(
                        group_type="slug",
                        group_key=slug,
                        category=category,
                        product_count=int(product_counts.get(category.id, 0) or 0),
                    )
                )
        return out

    def _export_csv(self, *, export_csv: str, rows: list[DuplicateEntry]) -> None:
        export_path = Path(export_csv).expanduser()
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with export_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "group_type",
                    "group_key",
                    "category_id",
                    "name",
                    "source",
                    "autodb_prd_id",
                    "parent_id",
                    "slug",
                    "product_count",
                    "is_active",
                    "show_in_header",
                    "created_at",
                    "updated_at",
                ],
            )
            writer.writeheader()
            for entry in rows:
                category = entry.category
                writer.writerow(
                    {
                        "group_type": entry.group_type,
                        "group_key": entry.group_key,
                        "category_id": str(category.id),
                        "name": category.name or "",
                        "source": category.source or "",
                        "autodb_prd_id": category.autodb_prd_id or "",
                        "parent_id": category.parent_id or "",
                        "slug": category.slug or "",
                        "product_count": entry.product_count,
                        "is_active": int(bool(category.is_active)),
                        "show_in_header": int(bool(category.show_in_header)),
                        "created_at": category.created_at.isoformat() if category.created_at else "",
                        "updated_at": category.updated_at.isoformat() if category.updated_at else "",
                    }
                )
