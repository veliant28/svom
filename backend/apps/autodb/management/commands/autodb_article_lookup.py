from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services.article_enrichment import AutoDbArticleEnrichmentService
from apps.autodb.services.article_lookup import AutoDbArticleLookupService
from apps.autodb.services.local_db_readiness import wait_for_local_autodb_ready


class Command(BaseCommand):
    help = "Lookup one brand+article in Auto_DB_Pro raw clone with local-first strategy and optional targeted enrichment."

    def add_arguments(self, parser):
        parser.add_argument("--brand", required=True, help="Brand from supplier price.")
        parser.add_argument("--article", required=True, help="Article from supplier price.")
        parser.add_argument("--enrich", action="store_true", help="Run targeted related-table enrichment for found article.")
        parser.add_argument(
            "--wait-for-autodb",
            type=int,
            default=0,
            help="Wait up to N seconds for local Auto_DB_Pro DB readiness before processing.",
        )

    def handle(self, *args, **options):
        brand = str(options.get("brand") or "").strip()
        article = str(options.get("article") or "").strip()
        wait_for_autodb = max(int(options.get("wait_for_autodb") or 0), 0)
        if not brand:
            raise CommandError("--brand is required")
        if not article:
            raise CommandError("--article is required")

        readiness = wait_for_local_autodb_ready(timeout_seconds=wait_for_autodb, interval_seconds=2.0)
        if not readiness.ready:
            raise CommandError(
                "Auto_DB_Pro local DB is not ready/recovering. Retry later. "
                f"host={readiness.host} port={readiness.port} database={readiness.database} "
                f"reason={readiness.reason} attempts={readiness.attempts} waited_seconds={readiness.waited_seconds} "
                f"error={readiness.error_message or '-'}"
            )

        lookup_service = AutoDbArticleLookupService()
        result = lookup_service.lookup(brand_name=brand, article=article)
        has_article_match = bool(result.canonical_article_number)

        self.stdout.write("Auto_DB_Pro article lookup:")
        self.stdout.write(f"- input_brand: {brand}")
        self.stdout.write(f"- input_article: {article}")
        self.stdout.write(f"- normalized_brand: {result.normalized_brand}")
        self.stdout.write(f"- normalized_article: {result.normalized_article}")
        self.stdout.write(f"- supplier_found: {result.supplier_id is not None} (source={result.supplier_source})")
        self.stdout.write(f"- article_found: {has_article_match} (source={result.article_source})")
        self.stdout.write(f"- found: {result.found}")
        self.stdout.write(f"- supplier_id: {result.supplier_id or '-'}")
        self.stdout.write(f"- article_id: {result.article_id or '-'}")
        self.stdout.write(f"- article_key: {result.article_key or '-'}")
        self.stdout.write(f"- canonical_brand: {result.canonical_brand or '-'}")
        self.stdout.write(f"- canonical_article_number: {result.canonical_article_number or '-'}")

        if result.populated_tables:
            self.stdout.write("- populated_tables:")
            for table, count in sorted(result.populated_tables.items()):
                self.stdout.write(f"  - {table}: {count}")

        if result.warnings:
            self.stdout.write("- warnings:")
            for warning in result.warnings:
                self.stdout.write(f"  - {warning}")

        if options.get("enrich"):
            if not result.found:
                raise CommandError("Cannot run --enrich: article is not found.")
            enrichment = AutoDbArticleEnrichmentService().enrich_article(
                article_id=result.article_id,
                supplier_id=result.supplier_id,
                article_number=result.canonical_article_number,
            )
            self.stdout.write("Auto_DB_Pro targeted enrichment:")
            for table, count in sorted(enrichment.populated_tables.items()):
                self.stdout.write(f"- {table}: {count}")
            if enrichment.skipped_tables:
                self.stdout.write(f"- skipped_tables: {','.join(enrichment.skipped_tables)}")
            if enrichment.warnings:
                self.stdout.write("- enrichment_warnings:")
                for warning in enrichment.warnings:
                    self.stdout.write(f"  - {warning}")
