from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.supplier_imports.parsers import ParserContext, get_parser
from apps.supplier_imports.parsers.utils import parse_table_rows, parse_xlsx_rows
from apps.supplier_imports.selectors import ensure_default_import_sources, get_import_source_by_code
from apps.supplier_imports.services.import_runner import preparation
from apps.supplier_imports.services.product_matcher import ProductMatcher


class Command(BaseCommand):
    help = "Diagnose supplier import parsing/matching decisions without persisting offers."

    def add_arguments(self, parser):
        parser.add_argument("--source", choices=["gpl", "utr"], required=True, help="Import source code.")
        parser.add_argument("--limit", type=int, default=50, help="Rows to diagnose.")
        parser.add_argument("--path", action="append", dest="paths", default=None, help="Optional explicit file path override.")
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV export path.")

    def handle(self, *args, **options):
        ensure_default_import_sources()
        source_code = str(options.get("source") or "").strip().lower()
        limit = max(int(options.get("limit") or 50), 1)
        export_csv = str(options.get("export_csv") or "").strip()
        paths = options.get("paths")

        source = get_import_source_by_code(source_code)
        files = preparation.collect_files(source=source, file_paths=paths)
        if not files:
            raise CommandError(f"No files found for source={source_code}.")

        file_path = files[0]
        rows, columns = self._read_rows_with_columns(file_path=file_path)
        if not rows:
            raise CommandError(f"No data rows found in file: {file_path}")

        parser = get_parser(source.parser_type)
        context = ParserContext(
            source_code=source.code,
            mapping_config=source.mapping_config,
            default_currency=source.default_currency,
        )
        parse_result = parser.parse_rows(rows, file_name=file_path.name, context=context)
        offers = list(parse_result.offers[:limit])

        matcher = ProductMatcher(lightweight_products=True)
        bootstrap_unmatched = self._bootstrap_default_for_source(source_code=source_code)

        diagnostics_rows: list[dict[str, str]] = []
        for index, offer in enumerate(offers, start=1):
            decision = matcher.evaluate_offer(
                article=offer.article,
                external_sku=offer.external_sku,
                brand_name=offer.brand_name,
                source=source,
                supplier=source.supplier,
            )
            supplier_sku = str((offer.external_sku or offer.article) or "").strip()
            parsed_brand = str(offer.brand_name or "").strip()
            parsed_article = str(offer.article or "").strip()
            parsed_name = str(offer.product_name or "").strip()
            validation_status, skip_reason = self._validation_status(
                price=offer.price,
                supplier_sku=supplier_sku,
                match_status=decision.status,
                matched_product_id=str(getattr(decision.matched_product, "id", "") or ""),
                bootstrap_unmatched=bootstrap_unmatched,
            )
            would_create_product = (
                validation_status == "valid"
                and decision.status != "auto_matched"
                and bootstrap_unmatched
            )
            would_create_offer = validation_status == "valid" and (
                decision.status == "auto_matched" or would_create_product
            )
            row = {
                "row_number": str(index),
                "raw_brand": str((offer.raw_payload or {}).get("Бренд") or (offer.raw_payload or {}).get("brand") or parsed_brand),
                "parsed_brand": parsed_brand,
                "raw_article": str((offer.raw_payload or {}).get("Артикул ТД") or (offer.raw_payload or {}).get("article") or parsed_article),
                "parsed_article": parsed_article,
                "raw_product_name": str((offer.raw_payload or {}).get("Найменування") or (offer.raw_payload or {}).get("name") or parsed_name),
                "parsed_product_name": parsed_name,
                "price": str(offer.price if offer.price is not None else ""),
                "stock": str(offer.stock_qty),
                "external_sku": str(offer.external_sku or ""),
                "image_url": str((offer.raw_payload or {}).get("Зображення товару") or (offer.raw_payload or {}).get("image") or ""),
                "validation_status": validation_status,
                "skip_reason": skip_reason,
                "error": skip_reason,
                "would_create_raw_offer": "yes" if validation_status == "valid" else "no",
                "would_create_supplier_offer": "yes" if would_create_offer else "no",
                "would_create_product": "yes" if would_create_product else "no",
                "match_status": str(decision.status or ""),
                "match_reason": str(decision.reason or ""),
                "matched_product_id": str(getattr(decision.matched_product, "id", "") or ""),
                "product_create_block_reason": self._product_create_block_reason(
                    validation_status=validation_status,
                    match_status=decision.status,
                    bootstrap_unmatched=bootstrap_unmatched,
                ),
            }
            diagnostics_rows.append(row)

        self.stdout.write("supplier import diagnose:")
        self.stdout.write(f"- source: {source.code}")
        self.stdout.write(f"- file: {file_path}")
        self.stdout.write(f"- file_rows_total: {len(rows)}")
        self.stdout.write(f"- parsed_offers_total: {len(parse_result.offers)}")
        self.stdout.write(f"- parse_issues_total: {len(parse_result.issues)}")
        self.stdout.write(f"- diagnosed_rows: {len(diagnostics_rows)}")
        self.stdout.write(f"- bootstrap_unmatched_default: {int(bootstrap_unmatched)}")
        self.stdout.write(f"- detected_columns_count: {len(columns)}")
        self.stdout.write("- detected_columns:")
        for column in columns[:80]:
            self.stdout.write(f"  - {column}")

        self.stdout.write("- sample_rows:")
        for row in diagnostics_rows[:20]:
            self.stdout.write(
                f"  - row={row['row_number']} brand={row['parsed_brand'] or '-'} article={row['parsed_article'] or '-'} "
                f"price={row['price'] or '-'} stock={row['stock']} match={row['match_status']} "
                f"would_raw={row['would_create_raw_offer']} would_offer={row['would_create_supplier_offer']} "
                f"would_product={row['would_create_product']} reason={row['skip_reason'] or '-'}"
            )

        if export_csv:
            self._export_csv(path=export_csv, rows=diagnostics_rows)
            self.stdout.write(f"- export_csv: {export_csv}")
        self.stdout.write("- UTR calls: 0")

    @staticmethod
    def _read_rows_with_columns(*, file_path: Path) -> tuple[list[tuple[int, dict[str, str]]], list[str]]:
        suffix = file_path.suffix.lower()
        if suffix == ".xlsx":
            rows = parse_xlsx_rows(file_path)
        else:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            rows = parse_table_rows(content)
        columns = list(rows[0][1].keys()) if rows else []
        return rows, columns

    @staticmethod
    def _bootstrap_default_for_source(*, source_code: str) -> bool:
        return source_code == "gpl"

    @staticmethod
    def _validation_status(
        *,
        price,
        supplier_sku: str,
        match_status: str,
        matched_product_id: str,
        bootstrap_unmatched: bool,
    ) -> tuple[str, str]:
        if price is None:
            return "invalid", "missing_price"
        if not supplier_sku:
            return "invalid", "missing_supplier_sku"
        if match_status == "auto_matched" and matched_product_id:
            return "valid", ""
        if bootstrap_unmatched:
            return "valid", ""
        return "invalid", match_status or "unmatched"

    @staticmethod
    def _product_create_block_reason(*, validation_status: str, match_status: str, bootstrap_unmatched: bool) -> str:
        if validation_status != "valid":
            return "invalid_row"
        if match_status == "auto_matched":
            return ""
        if bootstrap_unmatched:
            return ""
        return "bootstrap_disabled"

    @staticmethod
    def _export_csv(*, path: str, rows: list[dict[str, str]]) -> None:
        out = Path(path).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        if not rows:
            out.write_text("", encoding="utf-8")
            return

        with out.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
