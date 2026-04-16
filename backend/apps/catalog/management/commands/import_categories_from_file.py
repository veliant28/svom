from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.models import Category
from apps.catalog.services import (
    build_category_i18n_names,
    find_category_by_normalized_name,
    generate_unique_category_slug,
    sanitize_category_name,
)


def parse_category_paths(lines: Iterable[str]) -> list[tuple[str, ...]]:
    paths: list[tuple[str, ...]] = []
    current_root: str | None = None
    current_group: str | None = None
    next_indented_is_group = True

    for raw_line in lines:
        raw = raw_line.rstrip("\n")
        stripped = raw.strip()

        if not stripped:
            if current_root is not None:
                current_group = None
                next_indented_is_group = True
            continue

        if not raw.startswith((" ", "\t")):
            current_root = sanitize_category_name(stripped)
            current_group = None
            next_indented_is_group = True
            if current_root:
                paths.append((current_root,))
            continue

        if current_root is None:
            continue

        normalized = sanitize_category_name(stripped)
        if not normalized or normalized == "--":
            continue

        if next_indented_is_group:
            current_group = normalized
            paths.append((current_root, current_group))
            next_indented_is_group = False
            continue

        if current_group is None:
            current_group = normalized
            paths.append((current_root, current_group))
            continue

        paths.append((current_root, current_group, normalized))

    unique_paths: list[tuple[str, ...]] = []
    seen: set[tuple[str, ...]] = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        unique_paths.append(path)
    return unique_paths


class Command(BaseCommand):
    help = "Rebuild catalog categories from an indentation-based file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            dest="file",
            required=True,
            help="Path to categories source file.",
        )
        parser.add_argument(
            "--no-purge",
            action="store_true",
            help="Do not delete existing categories before import.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        file_path = Path(options["file"]).expanduser()
        if not file_path.is_absolute():
            file_path = (Path.cwd() / file_path).resolve()

        if not file_path.exists():
            raise CommandError(f"Categories file not found: {file_path}")

        try:
            raw_text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise CommandError(f"Cannot decode file as UTF-8: {file_path}") from exc

        paths = parse_category_paths(raw_text.splitlines())
        if not paths:
            raise CommandError("No category paths parsed from file.")

        if not options["no_purge"]:
            self._purge_categories()

        created = 0
        reactivated = 0
        reused = 0
        reserved_slugs: set[str] = set()

        for path in paths:
            parent: Category | None = None
            for raw_name in path:
                name = sanitize_category_name(raw_name)
                if not name:
                    continue

                existing = find_category_by_normalized_name(name=name, parent=parent)
                name_uk, name_ru, name_en = build_category_i18n_names(name)
                if existing is not None:
                    changed_fields: set[str] = set()
                    if not existing.is_active:
                        existing.is_active = True
                        changed_fields.add("is_active")

                    if not existing.name_uk:
                        existing.name_uk = name_uk
                        changed_fields.add("name_uk")
                    if not existing.name_ru or existing.name_ru in {existing.name, existing.name_uk}:
                        existing.name_ru = name_ru
                        changed_fields.add("name_ru")
                    if not existing.name_en or existing.name_en in {existing.name, existing.name_uk}:
                        existing.name_en = name_en
                        changed_fields.add("name_en")

                    if changed_fields:
                        existing.save(update_fields=changed_fields | {"updated_at"})
                        reactivated += 1
                    else:
                        reused += 1
                    parent = existing
                    continue

                parent = Category.objects.create(
                    parent=parent,
                    name=name,
                    name_uk=name_uk,
                    name_ru=name_ru,
                    name_en=name_en,
                    slug=generate_unique_category_slug(name=name, reserved_slugs=reserved_slugs),
                    is_active=True,
                )
                created += 1

        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Categories rebuild completed. "
                    f"Paths: {len(paths)}, created: {created}, reactivated: {reactivated}, reused: {reused}, "
                    f"total now: {Category.objects.count()}."
                ),
            ),
        )

    def _purge_categories(self) -> None:
        safety_counter = 0
        while Category.objects.exists():
            safety_counter += 1
            if safety_counter > 500:
                raise CommandError("Purge loop protection triggered while deleting categories.")

            leaves = Category.objects.filter(children__isnull=True)
            if not leaves.exists():
                raise CommandError("Unable to purge categories: no leaf nodes found.")
            leaves.delete()
