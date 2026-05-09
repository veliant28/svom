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
        parser.add_argument(
            "--autodb-enrich",
            action="store_true",
            help="Force-enable Auto_DB_Pro enrichment/link stage for this import run.",
        )
        parser.add_argument(
            "--no-autodb-enrich",
            action="store_true",
            help="Force-disable Auto_DB_Pro enrichment/link stage for this import run.",
        )
        parser.add_argument(
            "--update-product-names",
            action="store_true",
            help="Force-enable Product name update from Auto_DB_Pro for linked products.",
        )
        parser.add_argument(
            "--no-update-product-names",
            action="store_true",
            help="Force-disable Product name update from Auto_DB_Pro.",
        )
        parser.add_argument(
            "--update-product-images",
            action="store_true",
            help="Force-enable Product image update from GPL/Auto_DB_Pro.",
        )
        parser.add_argument(
            "--no-update-product-images",
            action="store_true",
            help="Force-disable Product image update from GPL/Auto_DB_Pro.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limit raw offers processed by Auto_DB_Pro post-step for each run (0 = no limit).",
        )
        parser.add_argument(
            "--row-limit",
            type=int,
            default=0,
            help="Limit parsed supplier rows processed for each import run (0 = no limit).",
        )
        parser.add_argument(
            "--autodb-allow-remote",
            action="store_true",
            help="Allow remote Auto-DB fallback in supplier import postprocess.",
        )
        parser.add_argument(
            "--autodb-no-remote",
            action="store_true",
            help="Disable remote Auto-DB fallback in supplier import postprocess.",
        )

    def handle(self, *args, **options):
        ensure_default_import_sources()

        source_codes = options.get("source") or []
        import_all = options.get("all", False)
        dry_run = options.get("dry_run", False)
        run_reindex = options.get("reindex", False)
        no_reprice = options.get("no_reprice", False)
        paths = options.get("paths")
        autodb_enrich_enabled = bool(options.get("autodb_enrich"))
        autodb_enrich_disabled = bool(options.get("no_autodb_enrich"))
        update_names_enabled = bool(options.get("update_product_names"))
        update_names_disabled = bool(options.get("no_update_product_names"))
        update_images_enabled = bool(options.get("update_product_images"))
        update_images_disabled = bool(options.get("no_update_product_images"))
        autodb_limit = max(int(options.get("limit") or 0), 0)
        row_limit = max(int(options.get("row_limit") or 0), 0)
        if row_limit == 0 and autodb_limit > 0:
            # Backward-compatible behavior for existing operator commands:
            # when only --limit is provided, cap parsed supplier rows as well.
            row_limit = autodb_limit
        autodb_allow_remote_enabled = bool(options.get("autodb_allow_remote"))
        autodb_no_remote_enabled = bool(options.get("autodb_no_remote"))

        if source_codes and import_all:
            raise CommandError("Use either --source or --all, not both.")
        if autodb_enrich_enabled and autodb_enrich_disabled:
            raise CommandError("Use either --autodb-enrich or --no-autodb-enrich, not both.")
        if update_names_enabled and update_names_disabled:
            raise CommandError("Use either --update-product-names or --no-update-product-names, not both.")
        if update_images_enabled and update_images_disabled:
            raise CommandError("Use either --update-product-images or --no-update-product-images, not both.")
        if autodb_allow_remote_enabled and autodb_no_remote_enabled:
            raise CommandError("Use either --autodb-allow-remote or --autodb-no-remote, not both.")

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

        autodb_enrich_override = None
        if autodb_enrich_enabled:
            autodb_enrich_override = True
        elif autodb_enrich_disabled:
            autodb_enrich_override = False

        update_names_override = None
        if update_names_enabled:
            update_names_override = True
        elif update_names_disabled:
            update_names_override = False

        update_images_override = None
        if update_images_enabled:
            update_images_override = True
        elif update_images_disabled:
            update_images_override = False

        autodb_remote_override = None
        if autodb_allow_remote_enabled:
            autodb_remote_override = True
        elif autodb_no_remote_enabled:
            autodb_remote_override = False

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
                autodb_enrich=autodb_enrich_override,
                update_product_names=update_names_override,
                update_product_images=update_images_override,
                autodb_limit=autodb_limit,
                autodb_allow_remote=autodb_remote_override,
                row_limit=row_limit,
            )

            self.stdout.write(self.style.SUCCESS(f"[{source.code}] run={result.run_id} status={result.status}"))
            for key, value in result.summary.items():
                self.stdout.write(f"  - {key}: {value}")
