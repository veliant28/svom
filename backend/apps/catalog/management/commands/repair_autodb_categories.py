from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from apps.catalog.models import Category, Product
from apps.catalog.services.manual_root_categories import manual_root_names_casefold


def _normalize_name(value: str) -> str:
    return " ".join(str(value or "").split()).casefold()


@dataclass(frozen=True)
class RepairAction:
    group_key: str
    canonical_id: str
    duplicate_id: str
    products_reassigned: int
    duplicate_deactivated: bool
    duplicate_hidden_from_nav: bool


class Command(BaseCommand):
    help = "Repair duplicated Auto_DB_Pro categories, keep Product.category links, and hide autodb categories from header."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Preview only, do not persist changes")
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV export path")

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        export_csv = str(options.get("export_csv") or "").strip()

        actions: list[RepairAction] = []
        nav_changed_autodb = 0
        nav_changed_curated = 0

        def run() -> None:
            nonlocal nav_changed_autodb, nav_changed_curated
            actions.extend(self._merge_autodb_duplicates(dry_run=dry_run))
            nav_changed_autodb = self._hide_autodb_in_navigation(dry_run=dry_run)
            nav_changed_curated = self._apply_curated_root_visibility(dry_run=dry_run)

        if dry_run:
            with transaction.atomic():
                run()
                transaction.set_rollback(True)
        else:
            with transaction.atomic():
                run()

        duplicate_groups_found = len({item.group_key for item in actions})
        categories_merged = len(actions)
        products_reassigned = sum(item.products_reassigned for item in actions)
        categories_deactivated = sum(1 for item in actions if item.duplicate_deactivated)
        categories_hidden = sum(1 for item in actions if item.duplicate_hidden_from_nav)

        self.stdout.write("Auto_DB_Pro category repair summary:")
        self.stdout.write(f"- dry_run: {int(dry_run)}")
        self.stdout.write(f"- duplicate_groups_found: {duplicate_groups_found}")
        self.stdout.write(f"- categories_merged: {categories_merged}")
        self.stdout.write(f"- products_reassigned: {products_reassigned}")
        self.stdout.write(f"- duplicate_categories_deactivated: {categories_deactivated}")
        self.stdout.write(f"- duplicate_categories_hidden_from_nav: {categories_hidden}")
        self.stdout.write(f"- autodb_categories_hidden_from_nav: {nav_changed_autodb}")
        self.stdout.write(f"- curated_root_nav_visibility_updates: {nav_changed_curated}")
        self.stdout.write("- manual_categories_untouched: 1")
        self.stdout.write("- deleted: 0")
        self.stdout.write("- UTR calls: 0")

        for item in actions[:80]:
            self.stdout.write(
                f"- merge group={item.group_key} canonical={item.canonical_id} duplicate={item.duplicate_id} "
                f"products_reassigned={item.products_reassigned} deactivated={int(item.duplicate_deactivated)} "
                f"hidden_from_nav={int(item.duplicate_hidden_from_nav)}"
            )

        if export_csv:
            self._export_csv(export_csv=export_csv, actions=actions)
            self.stdout.write(f"- csv_export: {export_csv}")

    def _merge_autodb_duplicates(self, *, dry_run: bool) -> list[RepairAction]:
        categories = list(
            Category.objects.filter(source=Category.SOURCE_AUTODB_PRO)
            .select_related("parent")
            .annotate(product_count=Count("products"))
            .order_by("created_at", "id")
        )
        if not categories:
            return []

        by_prd_id: dict[int, list[Category]] = {}
        for category in categories:
            if category.autodb_prd_id is None:
                continue
            key = int(category.autodb_prd_id)
            by_prd_id.setdefault(key, []).append(category)

        seen_ids: set[str] = set()
        actions: list[RepairAction] = []
        for key, group in by_prd_id.items():
            if len(group) <= 1:
                continue
            actions.extend(self._merge_group(group_key=f"prd:{key}", group=group, seen_ids=seen_ids, dry_run=dry_run))

        by_name: dict[str, list[Category]] = {}
        for category in categories:
            category_id = str(category.id)
            if category_id in seen_ids:
                continue
            if category.autodb_prd_id is not None:
                continue
            normalized = _normalize_name(category.name)
            if not normalized:
                continue
            parent_id = str(category.parent_id or "")
            key = f"name:{parent_id}:{normalized}"
            by_name.setdefault(key, []).append(category)

        for key, group in by_name.items():
            if len(group) <= 1:
                continue
            actions.extend(self._merge_group(group_key=key, group=group, seen_ids=seen_ids, dry_run=dry_run))

        return actions

    def _merge_group(
        self,
        *,
        group_key: str,
        group: list[Category],
        seen_ids: set[str],
        dry_run: bool,
    ) -> list[RepairAction]:
        if len(group) <= 1:
            return []

        canonical = self._choose_canonical(group)
        out: list[RepairAction] = []
        for category in group:
            category_id = str(category.id)
            seen_ids.add(category_id)
            if category_id == str(canonical.id):
                continue

            products_reassigned = Product.objects.filter(category=category).update(category=canonical)
            if dry_run:
                # Dry-run is wrapped in a rollback transaction, but we still want explicit intent in code.
                pass

            duplicate_deactivated = False
            duplicate_hidden_from_nav = False
            updates: list[str] = []
            if category.is_active:
                category.is_active = False
                duplicate_deactivated = True
                updates.append("is_active")
            if category.show_in_header:
                category.show_in_header = False
                duplicate_hidden_from_nav = True
                updates.append("show_in_header")
            if updates:
                category.save(update_fields=[*updates, "updated_at"])

            out.append(
                RepairAction(
                    group_key=group_key,
                    canonical_id=str(canonical.id),
                    duplicate_id=category_id,
                    products_reassigned=int(products_reassigned),
                    duplicate_deactivated=duplicate_deactivated,
                    duplicate_hidden_from_nav=duplicate_hidden_from_nav,
                )
            )
        return out

    def _choose_canonical(self, categories: Iterable[Category]) -> Category:
        items = list(categories)
        if not items:
            raise ValueError("categories collection is empty")

        def sort_key(category: Category):
            product_count = int(getattr(category, "product_count", 0) or 0)
            created_at = category.created_at
            return (
                0 if category.autodb_prd_id is not None else 1,
                -product_count,
                created_at.isoformat() if created_at else "",
                str(category.id),
            )

        return sorted(items, key=sort_key)[0]

    def _hide_autodb_in_navigation(self, *, dry_run: bool) -> int:
        qs = Category.objects.filter(source=Category.SOURCE_AUTODB_PRO, show_in_header=True)
        changed = qs.count()
        if changed and not dry_run:
            qs.update(show_in_header=False)
        if changed and dry_run:
            qs.update(show_in_header=False)
        return int(changed)

    def _apply_curated_root_visibility(self, *, dry_run: bool) -> int:
        curated_normalized = set(manual_root_names_casefold())
        changed = 0

        roots = list(
            Category.objects.filter(parent__isnull=True, is_active=True)
            .exclude(source=Category.SOURCE_AUTODB_PRO)
            .only("id", "name", "show_in_header")
        )
        for category in roots:
            should_show = _normalize_name(category.name) in curated_normalized
            if bool(category.show_in_header) == bool(should_show):
                continue
            category.show_in_header = should_show
            category.save(update_fields=["show_in_header", "updated_at"])
            changed += 1

        return changed

    def _export_csv(self, *, export_csv: str, actions: list[RepairAction]) -> None:
        export_path = Path(export_csv).expanduser()
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with export_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "group_key",
                    "canonical_id",
                    "duplicate_id",
                    "products_reassigned",
                    "duplicate_deactivated",
                    "duplicate_hidden_from_nav",
                ],
            )
            writer.writeheader()
            for action in actions:
                writer.writerow(
                    {
                        "group_key": action.group_key,
                        "canonical_id": action.canonical_id,
                        "duplicate_id": action.duplicate_id,
                        "products_reassigned": action.products_reassigned,
                        "duplicate_deactivated": int(action.duplicate_deactivated),
                        "duplicate_hidden_from_nav": int(action.duplicate_hidden_from_nav),
                    }
                )
