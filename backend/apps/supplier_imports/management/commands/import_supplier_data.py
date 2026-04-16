from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.supplier_imports.selectors import ensure_default_import_sources, get_active_import_sources, get_import_source_by_code
from apps.supplier_imports.services import SupplierImportRunner


class Command(BaseCommand):
    help = "Import supplier offers for UTR/GPL sources with optional dry-run and summary output."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            action="append",
            choices=["utr", "gpl"],
            default=None,
            help="Run import for specific source code. Can be passed multiple times.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Import all active sources.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and validate source rows without updating SupplierOffer data.",
        )
        parser.add_argument(
            "--reindex",
            action="store_true",
            help="Run product reindex for affected products after successful import.",
        )
        parser.add_argument(
            "--no-reprice",
            action="store_true",
            help="Skip repricing stage after import.",
        )
        parser.add_argument(
            "--path",
            action="append",
            dest="paths",
            default=None,
            help="Optional explicit file/directory path override for the selected source.",
        )

    def handle(self, *args, **options):
        ensure_default_import_sources()

        source_codes = options.get("source") or []
        import_all = options.get("all", False)
        dry_run = options.get("dry_run", False)
        run_reindex = options.get("reindex", False)
        no_reprice = options.get("no_reprice", False)
        paths = options.get("paths")

        if source_codes and import_all:
            raise CommandError("Use either --source or --all, not both.")

        if not source_codes and not import_all:
            import_all = True

        sources = []
        if import_all:
            sources = list(get_active_import_sources())
        else:
            for code in source_codes:
                source = get_import_source_by_code(code)
                sources.append(source)

        if not sources:
            raise CommandError("No import sources selected.")

        runner = SupplierImportRunner()
        self.stdout.write(f"Starting supplier import for {len(sources)} source(s)...")

        for source in sources:
            if paths and len(sources) > 1:
                raise CommandError("--path override can be used only with a single source.")

            result = runner.run_source(
                source=source,
                trigger="command:import_supplier_data",
                dry_run=dry_run,
                file_paths=paths,
                reprice=not no_reprice,
                reindex=run_reindex,
            )

            self.stdout.write(self.style.SUCCESS(f"[{source.code}] run={result.run_id} status={result.status}"))
            for key, value in result.summary.items():
                self.stdout.write(f"  - {key}: {value}")
