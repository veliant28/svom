from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.autodb.models import AutoDbMatchJob
from apps.autodb.services.article_number_normalizer import ArticleNumberNormalizer


class Command(BaseCommand):
    help = "Force Auto_DB matching job article source to Product.article for existing jobs."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", default=False)
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--chunk-size", type=int, default=1000)

    def handle(self, *args, **options):
        apply_changes = bool(options.get("apply"))
        limit = int(options.get("limit") or 0)
        chunk_size = max(int(options.get("chunk_size") or 1000), 100)
        normalizer = ArticleNumberNormalizer()

        queryset = AutoDbMatchJob.objects.select_related("product").order_by("id")
        if limit > 0:
            queryset = queryset[:limit]

        scanned = 0
        updated = 0
        skipped_missing_product_article = 0
        skipped_empty_canonical = 0
        unchanged = 0
        batch: list[AutoDbMatchJob] = []

        for job in queryset.iterator(chunk_size=chunk_size):
            scanned += 1
            product_article = str(getattr(job.product, "article", "") or "").strip()
            if not product_article:
                skipped_missing_product_article += 1
                continue

            canonical = normalizer.normalize(product_article).normalized
            if not canonical:
                skipped_empty_canonical += 1
                continue

            source_type = "product_article"
            if (
                str(job.article_source_type or "") == source_type
                and str(job.article_value or "") == product_article
                and str(job.canonical_article or "") == canonical
            ):
                unchanged += 1
                continue

            job.article_source_type = source_type
            job.article_value = product_article
            job.canonical_article = canonical
            if isinstance(job.metadata_json, dict):
                metadata = dict(job.metadata_json)
                metadata["article_reason"] = "forced Product.article source"
                metadata["article_confidence"] = 1.0
                job.metadata_json = metadata
            batch.append(job)
            updated += 1

            if apply_changes and len(batch) >= chunk_size:
                AutoDbMatchJob.objects.bulk_update(
                    batch,
                    ["article_source_type", "article_value", "canonical_article", "metadata_json", "updated_at"],
                    batch_size=chunk_size,
                )
                batch.clear()

        if apply_changes and batch:
            AutoDbMatchJob.objects.bulk_update(
                batch,
                ["article_source_type", "article_value", "canonical_article", "metadata_json", "updated_at"],
                batch_size=chunk_size,
            )

        self.stdout.write(
            self.style.SUCCESS(
                "autodb_matching_force_product_article_source "
                f"mode={'apply' if apply_changes else 'dry-run'} "
                f"scanned={scanned} updated={updated} unchanged={unchanged} "
                f"skipped_missing_product_article={skipped_missing_product_article} "
                f"skipped_empty_canonical={skipped_empty_canonical}"
            )
        )
