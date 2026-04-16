from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.models import Category
from apps.catalog.services import build_category_i18n_names, sanitize_category_name


class Command(BaseCommand):
    help = "Backfills category name_uk/name_ru/name_en using explicit manual dictionary."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing name_ru/name_en fields even if they are already filled.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        force = bool(options["force"])

        updated = 0
        untouched = 0

        for category in Category.objects.all().iterator(chunk_size=500):
            source_uk = sanitize_category_name(category.name_uk or category.name)
            if not source_uk:
                untouched += 1
                continue

            next_name_uk, next_name_ru, next_name_en = build_category_i18n_names(source_uk)
            changed_fields: set[str] = set()

            if not category.name_uk or force:
                if category.name_uk != next_name_uk:
                    category.name_uk = next_name_uk
                    changed_fields.add("name_uk")

            if force or not category.name_ru or category.name_ru in {category.name, category.name_uk}:
                if category.name_ru != next_name_ru:
                    category.name_ru = next_name_ru
                    changed_fields.add("name_ru")

            if force or not category.name_en or category.name_en in {category.name, category.name_uk}:
                if category.name_en != next_name_en:
                    category.name_en = next_name_en
                    changed_fields.add("name_en")

            if changed_fields:
                category.save(update_fields=changed_fields | {"updated_at"})
                updated += 1
            else:
                untouched += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Category i18n backfill completed. Updated: {updated}, untouched: {untouched}, total: {updated + untouched}.",
            ),
        )
