from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.autodb.services.clone_indexes import AutoDbCloneIndexService


class Command(BaseCommand):
    help = "Ensures technical indexes for Auto_DB_Pro raw clone tables."

    def add_arguments(self, parser):
        parser.add_argument("--vehicle-catalog", action="store_true", help="Ensure indexes for vehicle catalog clone tables.")
        parser.add_argument("--article-catalog", action="store_true", help="Ensure indexes for article catalog clone tables.")
        parser.add_argument("--only", type=str, default="", help="Single table name to limit index creation.")

    def handle(self, *args, **options):
        only = str(options.get("only") or "").strip()
        vehicle_catalog = bool(options.get("vehicle_catalog"))
        article_catalog = bool(options.get("article_catalog"))
        if only:
            tables = [only]
        else:
            tables = []
            if not vehicle_catalog and not article_catalog:
                self.stdout.write("No scope provided, defaulting to vehicle catalog indexes.")
                vehicle_catalog = True

        service = AutoDbCloneIndexService()
        if vehicle_catalog and article_catalog:
            results = service.ensure_indexes(tables=tables)
        elif article_catalog:
            results = service.ensure_article_catalog_indexes(tables=tables)
        else:
            results = service.ensure_vehicle_catalog_indexes(tables=tables)

        self.stdout.write("Auto_DB_Pro clone indexes ensure run:")
        for item in results:
            columns = ",".join(item.columns)
            suffix = f" ({item.message})" if item.message else ""
            self.stdout.write(f"- {item.table}.{columns}: {item.status} [{item.index_name}]{suffix}")

        self.stdout.write(self.style.SUCCESS("Auto_DB_Pro clone indexes ensure finished"))
