from django.core.management.base import BaseCommand

from apps.catalog.models import Product
from apps.catalog.services import resolve_autodb_article_name, sanitize_product_name
from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand


class Command(BaseCommand):
    help = "Backfill product i18n names from Auto-DB article_inf (fallback to current product.name)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing localized product names.",
        )

    def handle(self, *args, **options):
        force = bool(options.get("force"))
        updated = 0
        untouched = 0
        resolved_from_autodb = 0

        for product in Product.objects.select_related("brand").all().order_by("id").iterator(chunk_size=1000):
            article = normalize_article(product.article or "")
            brand = normalize_brand(getattr(product.brand, "name", ""))
            autodb_name = resolve_autodb_article_name(
                normalized_article=article,
                normalized_brand=brand,
                prefer_live=True,
            )
            normalized = sanitize_product_name(autodb_name or product.name or "")[:255]
            if not normalized:
                untouched += 1
                continue
            if autodb_name:
                resolved_from_autodb += 1

            changed_fields: set[str] = set()
            if autodb_name and product.name != normalized:
                product.name = normalized
                changed_fields.add("name")
            if force or not product.name_uk:
                if product.name_uk != normalized:
                    product.name_uk = normalized
                    changed_fields.add("name_uk")
            if force or not product.name_ru:
                if product.name_ru != normalized:
                    product.name_ru = normalized
                    changed_fields.add("name_ru")
            if force or not product.name_en:
                if product.name_en != normalized:
                    product.name_en = normalized
                    changed_fields.add("name_en")

            if changed_fields:
                product.save(update_fields=tuple(sorted(changed_fields | {"updated_at"})))
                updated += 1
            else:
                untouched += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Product i18n backfill completed. "
                f"Updated: {updated}, untouched: {untouched}, total: {updated + untouched}, "
                f"resolved_from_article_inf: {resolved_from_autodb}."
            )
        )
