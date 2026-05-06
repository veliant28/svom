from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.autodb.services.clone_runtime_status import get_passanger_car_trees_runtime_status
from apps.autodb.services.product_fitment_audit import AutoDbProductFitmentAuditService


class Command(BaseCommand):
    help = "Audit Auto_DB_Pro ProductFitments quality and distribution before public filtering enablement."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="Limit audited products.")
        parser.add_argument("--product-id", type=str, default="", help="Audit one Product UUID.")
        parser.add_argument("--sample", type=int, default=0, help="Random sample size of products with Auto_DB fitments.")
        parser.add_argument("--export-csv", type=str, default="", help="Export flat audit rows to CSV path.")
        parser.add_argument(
            "--persist-quality",
            action="store_true",
            help="Persist link quality status and fitment exclusion flags without deleting fitments.",
        )

    def handle(self, *args, **options):
        limit = max(int(options.get("limit") or 0), 0)
        sample = max(int(options.get("sample") or 0), 0)
        product_id = str(options.get("product_id") or "").strip()
        export_csv = str(options.get("export_csv") or "").strip()
        persist_quality = bool(options.get("persist_quality"))

        service = AutoDbProductFitmentAuditService()
        queryset = service.build_queryset(limit=limit, product_id=product_id, sample=sample)
        rows, summary = service.audit_queryset(queryset, persist_quality=persist_quality)
        runtime = get_passanger_car_trees_runtime_status(reconcile=True)

        self.stdout.write(
            "Auto_DB_Pro product fitment audit started "
            f"limit={limit} product_id={product_id or '-'} sample={sample} persist_quality={persist_quality}"
        )
        self.stdout.write("Auto_DB_Pro product fitment audit summary:")
        self.stdout.write(f"- audited_products: {summary.audited_products}")
        self.stdout.write(f"- total_fitments: {summary.total_fitments}")
        self.stdout.write(f"- min_fitments: {summary.min_fitments}")
        self.stdout.write(f"- max_fitments: {summary.max_fitments}")
        self.stdout.write(f"- avg_fitments: {summary.avg_fitments}")
        self.stdout.write(f"- median_fitments: {summary.median_fitments}")
        self.stdout.write(f"- suspicious_products: {summary.suspicious_products}")
        flagged_products = sum(1 for row in rows if row.suspicious_flags)
        self.stdout.write(f"- flagged_products_any_reason: {flagged_products}")
        self.stdout.write(f"- missing_passanger_cars: {summary.missing_passanger_car_count}")
        self.stdout.write(
            f"- passengercar_only_created_fitments: "
            f"{set(summary.autodb_fitment_linkage_counts.keys()) <= {'PassengerCar'} if summary.autodb_fitment_linkage_counts else True}"
        )

        self.stdout.write("- raw article_li linkageTypeId summary:")
        if not summary.linkage_type_counts:
            self.stdout.write("  - -")
        for linkage_type, count in sorted(summary.linkage_type_counts.items(), key=lambda item: (-item[1], item[0])):
            self.stdout.write(f"  - {linkage_type}: {count}")

        self.stdout.write("- created ProductFitment linkage_type summary:")
        if not summary.autodb_fitment_linkage_counts:
            self.stdout.write("  - -")
        for linkage_type, count in sorted(summary.autodb_fitment_linkage_counts.items(), key=lambda item: (-item[1], item[0])):
            self.stdout.write(f"  - {linkage_type}: {count}")

        self.stdout.write("- top products by fitment_count:")
        if not summary.top_products:
            self.stdout.write("  - -")
        for product_id_value, name_value, fitment_count in summary.top_products:
            self.stdout.write(f"  - product_id={product_id_value} name={name_value or '-'} fitment_count={fitment_count}")

        self.stdout.write("- sample Product -> vehicle labels:")
        if not summary.sample_rows:
            self.stdout.write("  - -")
        for row in summary.sample_rows:
            flags = ",".join(row.suspicious_flags) or "-"
            self.stdout.write(
                "  - "
                f"product_id={row.product_id} article_key={row.autodb_article_key or '-'} fitment_count={row.fitment_count} "
                f"sample_vehicle={row.sample_vehicle_label or '-'} suspicious_flags={flags}"
            )

        suspicious_link_rows = [row for row in rows if "suspicious_link" in row.suspicious_flags]
        self.stdout.write("- suspicious_link examples:")
        if not suspicious_link_rows:
            self.stdout.write("  - -")
        for row in suspicious_link_rows[:10]:
            self.stdout.write(
                "  - "
                f"product_id={row.product_id} article_key={row.autodb_article_key or '-'} "
                f"product_name={row.name_uk or row.name_ru or row.name_en or '-'} "
                f"autodb_article_title={row.autodb_article_title or '-'} autodb_prd_title={row.autodb_prd_title or '-'} "
                f"reason={row.suspicious_reason or '-'} "
                f"persisted_status={row.persisted_quality_status or '-'} excluded={row.persisted_excluded_from_public_filtering}"
            )

        non_blocking_flag_rows = [row for row in rows if row.suspicious_flags and "suspicious_link" not in row.suspicious_flags]
        self.stdout.write("- non_blocking audit flags:")
        if not non_blocking_flag_rows:
            self.stdout.write("  - -")
        for row in non_blocking_flag_rows[:10]:
            self.stdout.write(
                "  - "
                f"product_id={row.product_id} article_key={row.autodb_article_key or '-'} "
                f"product_name={row.name_uk or row.name_ru or row.name_en or '-'} "
                f"flags={','.join(row.suspicious_flags) or '-'}"
            )

        if persist_quality:
            persisted_rows = [row for row in rows if row.persisted_quality_status]
            self.stdout.write("- persisted quality summary:")
            self.stdout.write(f"  - persisted_rows: {len(persisted_rows)}")
            self.stdout.write(
                f"  - suspicious_or_manual_review: "
                f"{sum(1 for row in persisted_rows if row.persisted_excluded_from_public_filtering)}"
            )
            self.stdout.write(
                f"  - manual_overrides_preserved: "
                f"{sum(1 for row in persisted_rows if row.persisted_manual_override)}"
            )

        self.stdout.write("- passanger_car_trees actual status:")
        self.stdout.write(
            "  - "
            f"state_status={runtime.state_status} actual_status={runtime.actual_status} process_running={runtime.process_running} "
            f"pid={runtime.pid or '-'} processed={runtime.processed_rows} total={runtime.total_rows} "
            f"count={runtime.table_row_count} last_cursor={runtime.last_cursor or '-'} "
            f"reconciled={runtime.reconciled} reconcile_note={runtime.reconcile_note or '-'}"
        )

        if export_csv:
            path = service.export_csv(rows=rows, path=export_csv)
            self.stdout.write(f"- export_csv: {path}")

        self.stdout.write("- UTR calls: 0")
