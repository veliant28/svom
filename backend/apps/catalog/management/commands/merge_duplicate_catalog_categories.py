from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count

from apps.catalog.models import AutoDbPrdCategoryMap, Category, Product
from apps.catalog.services import canonical_specs_by_slug, find_semantic_category_under_parent, generate_unique_category_slug


@dataclass
class MergeRow:
    pair: str
    parent: str
    duplicate_id: str
    duplicate_name: str
    duplicate_slug: str
    duplicate_source: str
    duplicate_autodb_prd_id: str
    canonical_id: str
    canonical_name: str
    canonical_slug: str
    canonical_source: str
    canonical_autodb_prd_id: str
    products_to_move: int
    products_moved: int
    maps_to_repoint: int
    maps_repointed: int
    canonical_created: int
    duplicate_archived: int
    autodb_prd_id_preserved: int
    slug_name_updates: int
    conflict: str
    action: str


@dataclass
class MergeSummary:
    pairs_detected: int = 0
    pairs_resolved: int = 0
    products_to_move: int = 0
    products_moved: int = 0
    maps_to_repoint: int = 0
    maps_repointed: int = 0
    canonical_created: int = 0
    duplicate_archived: int = 0
    autodb_prd_id_preserved: int = 0
    slug_name_updates: int = 0
    conflicts: int = 0
    failed: int = 0
    duplicates_remaining: int = 0


class Command(BaseCommand):
    help = "Merge duplicate catalog categories into canonical categories by explicit pairs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--pairs",
            type=str,
            required=True,
            help='Comma-separated pairs in format "Old=>Canonical,Old2=>Canonical2"',
        )
        parser.add_argument("--dry-run", action="store_true", help="Preview only, do not write changes")
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV export path")

    def handle(self, *args, **options):
        pairs_raw = str(options.get("pairs") or "").strip()
        if not pairs_raw:
            raise CommandError("Provide --pairs")

        dry_run = bool(options.get("dry_run"))
        export_csv = str(options.get("export_csv") or "").strip()

        parsed_pairs = self._parse_pairs(pairs_raw)
        if not parsed_pairs:
            raise CommandError("No valid pairs parsed from --pairs")

        summary = MergeSummary()
        rows: list[MergeRow] = []

        def run() -> None:
            for duplicate_name, canonical_name in parsed_pairs:
                pair_key = f"{duplicate_name}=>{canonical_name}"
                pair_rows = self._merge_pair(
                    duplicate_name=duplicate_name,
                    canonical_name=canonical_name,
                    pair_key=pair_key,
                    dry_run=dry_run,
                    summary=summary,
                )
                rows.extend(pair_rows)

            summary.duplicates_remaining = self._count_remaining_duplicates(parsed_pairs)

        if dry_run:
            with transaction.atomic():
                run()
                transaction.set_rollback(True)
        else:
            with transaction.atomic():
                run()

        self.stdout.write("merge duplicate catalog categories summary:")
        self.stdout.write(f"- dry_run: {int(dry_run)}")
        self.stdout.write(f"- pairs_detected: {summary.pairs_detected}")
        self.stdout.write(f"- pairs_resolved: {summary.pairs_resolved}")
        self.stdout.write(f"- products_to_move: {summary.products_to_move}")
        self.stdout.write(f"- products_moved: {summary.products_moved}")
        self.stdout.write(f"- maps_to_repoint: {summary.maps_to_repoint}")
        self.stdout.write(f"- maps_repointed: {summary.maps_repointed}")
        self.stdout.write(f"- canonical_created: {summary.canonical_created}")
        self.stdout.write(f"- duplicate_archived: {summary.duplicate_archived}")
        self.stdout.write(f"- autodb_prd_id_preserved: {summary.autodb_prd_id_preserved}")
        self.stdout.write(f"- slug_name_updates: {summary.slug_name_updates}")
        self.stdout.write(f"- conflicts: {summary.conflicts}")
        self.stdout.write(f"- failed: {summary.failed}")
        self.stdout.write(f"- duplicates_remaining: {summary.duplicates_remaining}")
        self.stdout.write("- UTR calls=0")
        self.stdout.write("- price/stock changed=0")

        for row in rows:
            self.stdout.write(
                f"- pair={row.pair} parent={row.parent} duplicate_id={row.duplicate_id} canonical_id={row.canonical_id} "
                f"products_to_move={row.products_to_move} products_moved={row.products_moved} "
                f"maps_to_repoint={row.maps_to_repoint} maps_repointed={row.maps_repointed} "
                f"autodb_prd_id_preserved={row.autodb_prd_id_preserved} slug_name_updates={row.slug_name_updates} "
                f"archived={row.duplicate_archived} action={row.action} conflict={row.conflict or '-'}"
            )

        if export_csv:
            self._export_csv(path=export_csv, rows=rows)
            self.stdout.write(f"- csv_export: {export_csv}")

    def _parse_pairs(self, raw: str) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for chunk in raw.split(","):
            item = chunk.strip()
            if not item:
                continue
            if "=>" not in item:
                raise CommandError(f"Invalid pair format: {item}. Expected Old=>Canonical")
            left, right = item.split("=>", 1)
            old_name = left.strip()
            new_name = right.strip()
            if not old_name or not new_name:
                raise CommandError(f"Invalid pair format: {item}. Empty category name")
            out.append((old_name, new_name))
        return out

    def _merge_pair(
        self,
        *,
        duplicate_name: str,
        canonical_name: str,
        pair_key: str,
        dry_run: bool,
        summary: MergeSummary,
    ) -> list[MergeRow]:
        rows: list[MergeRow] = []

        duplicates = list(
            Category.objects.filter(name__iexact=duplicate_name)
            .select_related("parent")
            .annotate(product_count=Count("products"))
            .order_by("id")
        )
        if not duplicates:
            return rows

        for duplicate in duplicates:
            if duplicate.parent_id is None:
                continue
            parent = duplicate.parent
            if parent is None:
                continue

            summary.pairs_detected += 1
            conflict = ""
            action = "merged"

            canonical = self._find_or_create_canonical_for_parent(
                parent=parent,
                canonical_name=canonical_name,
                duplicate=duplicate,
                dry_run=dry_run,
            )
            canonical_created = 1 if canonical[1] else 0
            canonical_category = canonical[0]
            if canonical_category is None:
                summary.failed += 1
                summary.conflicts += 1
                rows.append(
                    self._build_row(
                        pair=pair_key,
                        parent_name=str(parent.name or ""),
                        duplicate=duplicate,
                        canonical=None,
                        products_to_move=0,
                        products_moved=0,
                        maps_to_repoint=0,
                        maps_repointed=0,
                        canonical_created=0,
                        duplicate_archived=0,
                        autodb_prd_id_preserved=0,
                        slug_name_updates=0,
                        conflict="canonical_not_found_or_created",
                        action="failed",
                    )
                )
                continue

            summary.canonical_created += canonical_created

            if str(canonical_category.id) == str(duplicate.id):
                action = "already_canonical"
                rows.append(
                    self._build_row(
                        pair=pair_key,
                        parent_name=str(parent.name or ""),
                        duplicate=duplicate,
                        canonical=canonical_category,
                        products_to_move=0,
                        products_moved=0,
                        maps_to_repoint=0,
                        maps_repointed=0,
                        canonical_created=canonical_created,
                        duplicate_archived=0,
                        autodb_prd_id_preserved=0,
                        slug_name_updates=0,
                        conflict="",
                        action=action,
                    )
                )
                continue

            products_to_move = Product.objects.filter(category=duplicate).count()
            maps_to_repoint = AutoDbPrdCategoryMap.objects.filter(category=duplicate).count()
            summary.products_to_move += int(products_to_move)
            summary.maps_to_repoint += int(maps_to_repoint)

            products_moved = Product.objects.filter(category=duplicate).update(category=canonical_category)
            maps_repointed = AutoDbPrdCategoryMap.objects.filter(category=duplicate).update(category=canonical_category)
            summary.products_moved += int(products_moved)
            summary.maps_repointed += int(maps_repointed)

            canonical_updated_fields = self._ensure_canonical_display(
                canonical=canonical_category,
                canonical_name=canonical_name,
                duplicate=duplicate,
            )
            slug_name_updates = len(canonical_updated_fields)
            if canonical_updated_fields:
                canonical_category.save(update_fields=canonical_updated_fields + ["updated_at"])

            autodb_preserved = 0
            if duplicate.autodb_prd_id and not canonical_category.autodb_prd_id:
                moved_prd_id = int(duplicate.autodb_prd_id)
                duplicate.autodb_prd_id = None
                duplicate.save(update_fields=["autodb_prd_id", "updated_at"])
                canonical_category.autodb_prd_id = moved_prd_id
                canonical_category.save(update_fields=["autodb_prd_id", "updated_at"])
                autodb_preserved = 1
            elif duplicate.autodb_prd_id and canonical_category.autodb_prd_id and duplicate.autodb_prd_id != canonical_category.autodb_prd_id:
                conflict = f"autodb_prd_id_conflict:{duplicate.autodb_prd_id}!={canonical_category.autodb_prd_id}"
                summary.conflicts += 1

            self._merge_debug_payload(canonical=canonical_category, duplicate=duplicate)

            archived = self._archive_duplicate(duplicate=duplicate, canonical=canonical_category)
            if archived:
                summary.duplicate_archived += 1

            if autodb_preserved:
                summary.autodb_prd_id_preserved += 1
            summary.slug_name_updates += slug_name_updates
            summary.pairs_resolved += 1

            rows.append(
                self._build_row(
                    pair=pair_key,
                    parent_name=str(parent.name or ""),
                    duplicate=duplicate,
                    canonical=canonical_category,
                    products_to_move=int(products_to_move),
                    products_moved=int(products_moved),
                    maps_to_repoint=int(maps_to_repoint),
                    maps_repointed=int(maps_repointed),
                    canonical_created=canonical_created,
                    duplicate_archived=1 if archived else 0,
                    autodb_prd_id_preserved=autodb_preserved,
                    slug_name_updates=slug_name_updates,
                    conflict=conflict,
                    action=action,
                )
            )

        return rows

    def _find_or_create_canonical_for_parent(
        self,
        *,
        parent: Category,
        canonical_name: str,
        duplicate: Category,
        dry_run: bool,
    ) -> tuple[Category | None, bool]:
        existing = (
            Category.objects.filter(parent=parent, name__iexact=canonical_name).exclude(id=duplicate.id).order_by("id").first()
        )
        if existing is None:
            existing = find_semantic_category_under_parent(parent=parent, name=canonical_name, include_inactive=True)
            if existing is not None and str(existing.id) == str(duplicate.id):
                existing = None
        if existing is None:
            existing = self._find_global_canonical(canonical_name=canonical_name, duplicate=duplicate)
        if existing is not None:
            return existing, False

        # Create canonical child only if missing under the same parent.
        spec = self._canonical_spec_for_name(canonical_name=canonical_name)
        slug = spec.canonical_slug if spec is not None else generate_unique_category_slug(name=canonical_name)
        if Category.objects.filter(slug=slug).exclude(parent=parent).exists() or Category.objects.filter(slug=slug, parent=parent).exclude(id=duplicate.id).exists():
            slug = generate_unique_category_slug(name=canonical_name, preferred_slug=slug)

        created = Category.objects.create(
            parent=parent,
            slug=slug,
            name=spec.name_ru if spec is not None else canonical_name,
            name_uk=spec.name_uk if spec is not None else canonical_name,
            name_ru=spec.name_ru if spec is not None else canonical_name,
            name_en=spec.name_en if spec is not None else canonical_name,
            source=Category.SOURCE_MANUAL,
            show_in_header=False,
            is_active=True,
        )
        return created, True

    def _find_global_canonical(self, *, canonical_name: str, duplicate: Category) -> Category | None:
        spec = self._canonical_spec_for_name(canonical_name=canonical_name)

        qs = Category.objects.exclude(id=duplicate.id).order_by("-is_active", "id")
        if spec is not None:
            by_slug = qs.filter(slug=spec.canonical_slug).first()
            if by_slug is not None:
                return by_slug

        exact = qs.filter(name__iexact=canonical_name).first()
        if exact is not None:
            return exact
        return None

    def _canonical_spec_for_name(self, *, canonical_name: str):
        specs = canonical_specs_by_slug().values()
        normalized = " ".join(str(canonical_name or "").split()).casefold()
        for spec in specs:
            names = {
                " ".join(spec.name_uk.split()).casefold(),
                " ".join(spec.name_ru.split()).casefold(),
                " ".join(spec.name_en.split()).casefold(),
            }
            if normalized in names:
                return spec
        return None

    def _ensure_canonical_display(self, *, canonical: Category, canonical_name: str, duplicate: Category) -> list[str]:
        updates: list[str] = []
        spec = self._canonical_spec_for_name(canonical_name=canonical_name)

        if spec is not None:
            desired_name = spec.name_ru
            desired_uk = spec.name_uk
            desired_ru = spec.name_ru
            desired_en = spec.name_en
            desired_slug = spec.canonical_slug
        else:
            desired_name = canonical_name
            desired_uk = canonical_name
            desired_ru = canonical_name
            desired_en = canonical.name_en or ""
            desired_slug = canonical.slug

        if canonical.name != desired_name:
            canonical.name = desired_name
            updates.append("name")
        if canonical.name_uk != desired_uk:
            canonical.name_uk = desired_uk
            updates.append("name_uk")
        if canonical.name_ru != desired_ru:
            canonical.name_ru = desired_ru
            updates.append("name_ru")
        if desired_en and canonical.name_en != desired_en:
            canonical.name_en = desired_en
            updates.append("name_en")

        if canonical.slug != desired_slug:
            slug_conflict = Category.objects.filter(slug=desired_slug).exclude(id=canonical.id).first()
            if slug_conflict is not None and str(slug_conflict.id) == str(duplicate.id):
                # Free desired slug by archiving duplicate slug first.
                self._retire_slug(duplicate)
                duplicate.save(update_fields=["slug", "updated_at"])
                slug_conflict = None
            if slug_conflict is None:
                canonical.slug = desired_slug
                updates.append("slug")

        if not canonical.is_active:
            canonical.is_active = True
            updates.append("is_active")
        if canonical.show_in_header:
            canonical.show_in_header = False
            updates.append("show_in_header")

        return list(dict.fromkeys(updates))

    def _merge_debug_payload(self, *, canonical: Category, duplicate: Category) -> None:
        payload = canonical.source_payload if isinstance(canonical.source_payload, dict) else {}
        merged = payload.get("merged_from_categories")
        if not isinstance(merged, list):
            merged = []

        merged.append(
            {
                "id": str(duplicate.id),
                "name": str(duplicate.name or ""),
                "slug": str(duplicate.slug or ""),
                "source": str(duplicate.source or ""),
                "autodb_prd_id": duplicate.autodb_prd_id,
                "source_hash": str(duplicate.source_hash or ""),
                "source_payload": duplicate.source_payload if isinstance(duplicate.source_payload, dict) else {},
            }
        )
        payload["merged_from_categories"] = merged

        updates: list[str] = []
        if canonical.source_payload != payload:
            canonical.source_payload = payload
            updates.append("source_payload")
        if not canonical.source_hash and duplicate.source_hash:
            canonical.source_hash = duplicate.source_hash
            updates.append("source_hash")

        if updates:
            canonical.save(update_fields=updates + ["updated_at"])

    def _retire_slug(self, category: Category) -> None:
        suffix = str(category.id).replace("-", "")[:8]
        base = str(category.slug or "category")
        candidate = f"{base}-merged-{suffix}"[:220]
        index = 2
        while Category.objects.filter(slug=candidate).exclude(id=category.id).exists():
            candidate = f"{base}-merged-{suffix}-{index}"[:220]
            index += 1
        category.slug = candidate

    def _archive_duplicate(self, *, duplicate: Category, canonical: Category) -> bool:
        updates: list[str] = []

        if duplicate.autodb_prd_id:
            duplicate.autodb_prd_id = None
            updates.append("autodb_prd_id")

        if duplicate.is_active:
            duplicate.is_active = False
            updates.append("is_active")
        if duplicate.show_in_header:
            duplicate.show_in_header = False
            updates.append("show_in_header")

        self._retire_slug(duplicate)
        updates.append("slug")

        merged_name = f"{duplicate.name} [merged->{canonical.name}]"[:180]
        if duplicate.name != merged_name:
            duplicate.name = merged_name
            updates.append("name")

        if duplicate.parent_id != canonical.parent_id:
            duplicate.parent = canonical.parent
            updates.append("parent")

        duplicate.save(update_fields=list(dict.fromkeys(updates + ["updated_at"])))
        return True

    def _count_remaining_duplicates(self, parsed_pairs: list[tuple[str, str]]) -> int:
        remaining = 0
        for duplicate_name, canonical_name in parsed_pairs:
            qs = Category.objects.filter(name__iexact=duplicate_name, is_active=True, parent__isnull=False)
            for category in qs.select_related("parent"):
                if Category.objects.filter(
                    parent=category.parent,
                    name__iexact=canonical_name,
                    is_active=True,
                ).exclude(id=category.id).exists():
                    remaining += 1
        return remaining

    def _build_row(
        self,
        *,
        pair: str,
        parent_name: str,
        duplicate: Category,
        canonical: Category | None,
        products_to_move: int,
        products_moved: int,
        maps_to_repoint: int,
        maps_repointed: int,
        canonical_created: int,
        duplicate_archived: int,
        autodb_prd_id_preserved: int,
        slug_name_updates: int,
        conflict: str,
        action: str,
    ) -> MergeRow:
        return MergeRow(
            pair=pair,
            parent=parent_name,
            duplicate_id=str(duplicate.id),
            duplicate_name=str(duplicate.name or ""),
            duplicate_slug=str(duplicate.slug or ""),
            duplicate_source=str(duplicate.source or ""),
            duplicate_autodb_prd_id=str(duplicate.autodb_prd_id or ""),
            canonical_id=str(getattr(canonical, "id", "") or ""),
            canonical_name=str(getattr(canonical, "name", "") or ""),
            canonical_slug=str(getattr(canonical, "slug", "") or ""),
            canonical_source=str(getattr(canonical, "source", "") or ""),
            canonical_autodb_prd_id=str(getattr(canonical, "autodb_prd_id", "") or ""),
            products_to_move=products_to_move,
            products_moved=products_moved,
            maps_to_repoint=maps_to_repoint,
            maps_repointed=maps_repointed,
            canonical_created=canonical_created,
            duplicate_archived=duplicate_archived,
            autodb_prd_id_preserved=autodb_prd_id_preserved,
            slug_name_updates=slug_name_updates,
            conflict=conflict,
            action=action,
        )

    def _export_csv(self, *, path: str, rows: list[MergeRow]) -> None:
        export_path = Path(path).expanduser()
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with export_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "pair",
                    "parent",
                    "duplicate_id",
                    "duplicate_name",
                    "duplicate_slug",
                    "duplicate_source",
                    "duplicate_autodb_prd_id",
                    "canonical_id",
                    "canonical_name",
                    "canonical_slug",
                    "canonical_source",
                    "canonical_autodb_prd_id",
                    "products_to_move",
                    "products_moved",
                    "maps_to_repoint",
                    "maps_repointed",
                    "canonical_created",
                    "duplicate_archived",
                    "autodb_prd_id_preserved",
                    "slug_name_updates",
                    "conflict",
                    "action",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "pair": row.pair,
                        "parent": row.parent,
                        "duplicate_id": row.duplicate_id,
                        "duplicate_name": row.duplicate_name,
                        "duplicate_slug": row.duplicate_slug,
                        "duplicate_source": row.duplicate_source,
                        "duplicate_autodb_prd_id": row.duplicate_autodb_prd_id,
                        "canonical_id": row.canonical_id,
                        "canonical_name": row.canonical_name,
                        "canonical_slug": row.canonical_slug,
                        "canonical_source": row.canonical_source,
                        "canonical_autodb_prd_id": row.canonical_autodb_prd_id,
                        "products_to_move": row.products_to_move,
                        "products_moved": row.products_moved,
                        "maps_to_repoint": row.maps_to_repoint,
                        "maps_repointed": row.maps_repointed,
                        "canonical_created": row.canonical_created,
                        "duplicate_archived": row.duplicate_archived,
                        "autodb_prd_id_preserved": row.autodb_prd_id_preserved,
                        "slug_name_updates": row.slug_name_updates,
                        "conflict": row.conflict,
                        "action": row.action,
                    }
                )
