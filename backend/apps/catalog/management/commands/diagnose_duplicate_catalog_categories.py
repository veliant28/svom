from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.catalog.models import Category
from apps.catalog.services import canonical_specs_by_slug, resolve_canonical_spec_for_name
from apps.catalog.services.category_management import normalized_category_name


@dataclass(frozen=True)
class DuplicateRow:
    category_id: str
    name: str
    slug: str
    parent: str
    source: str
    autodb_prd_id: int | None
    product_count: int
    is_active: bool
    show_in_header: bool
    suggested_canonical_id: str
    merge_action: str
    semantic_key: str


class Command(BaseCommand):
    help = "Diagnose semantic duplicate categories under the same parent."

    def add_arguments(self, parser):
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV export path")

    def handle(self, *args, **options):
        export_csv = str(options.get("export_csv") or "").strip()
        categories = list(
            Category.objects.select_related("parent")
            .annotate(product_count=Count("products"))
            .order_by("parent_id", "name", "id")
        )
        by_group: dict[tuple[str, str], list[Category]] = {}
        for category in categories:
            if category.parent_id is None:
                continue
            semantic = self._semantic_key(str(category.name or ""))
            if not semantic:
                continue
            key = (str(category.parent_id), semantic)
            by_group.setdefault(key, []).append(category)

        rows: list[DuplicateRow] = []
        duplicate_groups = 0
        for (parent_id, semantic_key), group in by_group.items():
            if len(group) <= 1:
                continue
            duplicate_groups += 1
            canonical = self._choose_canonical(group=group)
            parent_name = str(getattr(canonical.parent, "name", "") or parent_id)
            for category in group:
                is_canonical = str(category.id) == str(canonical.id)
                rows.append(
                    DuplicateRow(
                        category_id=str(category.id),
                        name=str(category.name or ""),
                        slug=str(category.slug or ""),
                        parent=parent_name,
                        source=str(category.source or ""),
                        autodb_prd_id=category.autodb_prd_id,
                        product_count=int(getattr(category, "product_count", 0) or 0),
                        is_active=bool(category.is_active),
                        show_in_header=bool(category.show_in_header),
                        suggested_canonical_id=str(canonical.id),
                        merge_action="keep_canonical" if is_canonical else "move_products_to_canonical",
                        semantic_key=semantic_key,
                    )
                )

        rows.sort(key=lambda item: (item.parent.casefold(), item.semantic_key, item.name.casefold(), item.category_id))

        self.stdout.write("duplicate catalog categories diagnosis summary:")
        self.stdout.write(f"- duplicate_groups: {duplicate_groups}")
        self.stdout.write(f"- duplicate_categories: {len(rows)}")
        self.stdout.write("- UTR calls: 0")
        for row in rows[:200]:
            self.stdout.write(
                f"- category_id={row.category_id} name={row.name} slug={row.slug} parent={row.parent} "
                f"source={row.source} autodb_prd_id={row.autodb_prd_id or '-'} product_count={row.product_count} "
                f"is_active={int(row.is_active)} show_in_header={int(row.show_in_header)} "
                f"suggested_canonical_id={row.suggested_canonical_id} merge_action={row.merge_action}"
            )

        if export_csv:
            self._export_csv(path=export_csv, rows=rows)
            self.stdout.write(f"- csv_export: {export_csv}")

    def _semantic_key(self, name: str) -> str:
        normalized = normalized_category_name(name)
        if not normalized:
            return ""

        canonical_spec = resolve_canonical_spec_for_name(name)
        if canonical_spec is not None:
            return f"canonical:{canonical_spec.canonical_slug}"

        for suffix in ("es", "s", "ы", "и", "а", "я"):
            if normalized.endswith(suffix) and len(normalized) > len(suffix) + 4:
                return normalized[: -len(suffix)]
        return normalized

    def _choose_canonical(self, *, group: list[Category]) -> Category:
        spec_by_slug = canonical_specs_by_slug()
        for category in group:
            spec = spec_by_slug.get(str(category.slug or ""))
            if spec is not None:
                return category

        def sort_key(item: Category) -> tuple[int, int, int, str]:
            return (
                0 if item.source == Category.SOURCE_MANUAL else 1,
                -int(getattr(item, "product_count", 0) or 0),
                0 if item.autodb_prd_id is None else 1,
                str(item.id),
            )

        return sorted(group, key=sort_key)[0]

    def _export_csv(self, *, path: str, rows: list[DuplicateRow]) -> None:
        export_path = Path(path).expanduser()
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with export_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "category_id",
                    "name",
                    "slug",
                    "parent",
                    "source",
                    "autodb_prd_id",
                    "product_count",
                    "is_active",
                    "show_in_header",
                    "suggested_canonical_id",
                    "merge_action",
                    "semantic_key",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "category_id": row.category_id,
                        "name": row.name,
                        "slug": row.slug,
                        "parent": row.parent,
                        "source": row.source,
                        "autodb_prd_id": row.autodb_prd_id or "",
                        "product_count": row.product_count,
                        "is_active": int(row.is_active),
                        "show_in_header": int(row.show_in_header),
                        "suggested_canonical_id": row.suggested_canonical_id,
                        "merge_action": row.merge_action,
                        "semantic_key": row.semantic_key,
                    }
                )
