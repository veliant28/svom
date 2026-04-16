from __future__ import annotations

from pathlib import Path
from typing import Iterable

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.supplier_imports.selectors import ensure_default_import_sources, get_import_source_by_code
from apps.supplier_imports.services.categorized_mapping_operational_service import (
    CategorizedMappingOperationalImportService,
    CategorizedOperationalRunResult,
)

_SUPPORTED_SUPPLIERS = ("gpl", "utr")


class Command(BaseCommand):
    help = "Import category mappings from categorized supplier XLSX files into SupplierRawOffer records."

    def add_arguments(self, parser):
        parser.add_argument(
            "--supplier",
            action="append",
            choices=_SUPPORTED_SUPPLIERS,
            default=None,
            help="Supplier code filter. Can be passed multiple times.",
        )
        parser.add_argument(
            "--file",
            action="append",
            dest="files",
            default=None,
            help="Explicit categorized XLSX file path. Can be passed multiple times.",
        )
        parser.add_argument(
            "--exports-dir",
            default="",
            help="Directory with categorized exports. Defaults to <project_root>/category_mapping_exports.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Bulk update batch size.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run import in a DB transaction and rollback all changes.",
        )
        parser.add_argument(
            "--no-strict-supplier-match",
            action="store_true",
            help="Do not enforce supplier code check between XLSX row and SupplierRawOffer.source/supplier.",
        )

    def handle(self, *args, **options):
        ensure_default_import_sources()
        supplier_codes = {
            str(item).strip().lower()
            for item in (options.get("supplier") or _SUPPORTED_SUPPLIERS)
            if str(item).strip()
        }
        file_paths = self._resolve_input_files(
            files=options.get("files") or [],
            exports_dir=options.get("exports_dir") or "",
            supplier_codes=supplier_codes,
        )
        batch_size = max(100, int(options.get("batch_size") or 1000))
        dry_run = bool(options.get("dry_run"))
        strict_supplier_match = not bool(options.get("no_strict_supplier_match"))
        grouped_paths = self._group_files_for_suppliers(file_paths=file_paths, supplier_codes=supplier_codes)

        self.stdout.write(
            "Starting categorized category import: "
            f"files={len(file_paths)}, suppliers={sorted(supplier_codes)}, dry_run={dry_run}, batch_size={batch_size}"
        )
        for path in file_paths:
            self.stdout.write(f"  - {path}")

        service = CategorizedMappingOperationalImportService(batch_size=batch_size)
        with transaction.atomic():
            results: list[CategorizedOperationalRunResult] = []
            for supplier_code in sorted(supplier_codes):
                source = get_import_source_by_code(supplier_code)
                source_files = grouped_paths.get(supplier_code) or file_paths
                self.stdout.write(
                    f"[{supplier_code}] importing categorized mappings from {len(source_files)} file(s)..."
                )
                result = service.run_for_source(
                    source=source,
                    file_paths=source_files,
                    supplier_code=supplier_code,
                    dry_run=dry_run,
                    strict_supplier_match=strict_supplier_match,
                )
                results.append(result)
                self._print_source_result(result=result)

            self._print_totals(results=results)
            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("Dry-run mode enabled: transaction rolled back."))

    def _resolve_input_files(self, *, files: list[str], exports_dir: str, supplier_codes: set[str]) -> list[Path]:
        if files:
            paths = [Path(item).expanduser().resolve() for item in files if str(item).strip()]
        else:
            base_dir = self._resolve_exports_dir(raw_dir=exports_dir)
            paths = [base_dir / f"supplier_price_categorized_{code}.xlsx" for code in sorted(supplier_codes)]

        missing = [path for path in paths if not path.exists()]
        if missing:
            missing_text = "\n".join(f"- {path}" for path in missing)
            raise CommandError(f"Input categorized file(s) not found:\n{missing_text}")

        if not paths:
            raise CommandError("No categorized files selected for import.")
        return paths

    def _group_files_for_suppliers(self, *, file_paths: list[Path], supplier_codes: set[str]) -> dict[str, list[Path]]:
        grouped: dict[str, list[Path]] = {code: [] for code in supplier_codes}
        fallback: list[Path] = []
        for file_path in file_paths:
            inferred = self._infer_supplier_from_name(file_path.name)
            if inferred and inferred in grouped:
                grouped[inferred].append(file_path)
            else:
                fallback.append(file_path)

        if fallback:
            for supplier_code in supplier_codes:
                grouped[supplier_code].extend(fallback)

        return grouped

    def _resolve_exports_dir(self, *, raw_dir: str) -> Path:
        if raw_dir.strip():
            return Path(raw_dir).expanduser().resolve()

        project_root = Path(settings.BASE_DIR).resolve().parent
        return (project_root / "category_mapping_exports").resolve()

    def _print_source_result(self, *, result: CategorizedOperationalRunResult) -> None:
        stats = result.stats
        self.stdout.write(
            self.style.SUCCESS(
                f"[{result.source_code}] run={result.run_id} status={result.run_status}"
            )
        )
        self.stdout.write(f"  files_processed: {stats.files_processed}")
        self.stdout.write(f"  rows_total: {stats.rows_total}")
        self.stdout.write(f"  rows_parsed: {stats.rows_parsed}")
        self.stdout.write(f"  rows_mapped: {stats.rows_mapped}")
        self.stdout.write(f"  rows_updated: {stats.rows_updated}")
        self.stdout.write(f"  rows_unchanged: {stats.rows_unchanged}")
        self.stdout.write(f"  mappings_overwritten: {stats.mappings_overwritten}")
        self.stdout.write(f"  errors_count: {stats.errors_count}")
        self.stdout.write(f"  rows_not_found: {stats.rows_not_found}")
        self.stdout.write(f"  rows_supplier_mismatch: {stats.rows_supplier_mismatch}")
        self.stdout.write(f"  rows_unresolved_category: {stats.rows_unresolved_category}")
        self.stdout.write(f"  categories_created: {stats.categories_created}")
        self.stdout.write(f"  categories_reactivated: {stats.categories_reactivated}")
        self.stdout.write("  category_status_counts:")
        for key in (
            "manual_mapped",
            "auto_mapped",
            "needs_review",
            "unmapped",
        ):
            self.stdout.write(f"    - {key}: {result.category_status_counts.get(key, 0)}")

    def _print_totals(self, *, results: Iterable[CategorizedOperationalRunResult]) -> None:
        result_list = list(results)
        total_rows = sum(item.stats.rows_parsed for item in result_list)
        total_updated = sum(item.stats.rows_updated for item in result_list)
        total_errors = sum(item.stats.errors_count for item in result_list)
        total_overwritten = sum(item.stats.mappings_overwritten for item in result_list)
        total_categories_created = sum(item.stats.categories_created for item in result_list)

        self.stdout.write(self.style.SUCCESS("Categorized import (all suppliers) completed."))
        self.stdout.write(f"total_rows: {total_rows}")
        self.stdout.write(f"total_rows_updated: {total_updated}")
        self.stdout.write(f"total_errors: {total_errors}")
        self.stdout.write(f"total_mappings_overwritten: {total_overwritten}")
        self.stdout.write(f"total_categories_created: {total_categories_created}")

    @staticmethod
    def _infer_supplier_from_name(file_name: str) -> str | None:
        normalized = file_name.lower()
        if "gpl" in normalized:
            return "gpl"
        if "utr" in normalized:
            return "utr"
        return None
