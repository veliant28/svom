from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.catalog.models import AutoDbProductLinkQuality, Product
from apps.compatibility.models import ProductFitment


@dataclass
class PersistRowResult:
    product_id: str
    article_key: str
    suspicious: bool
    skipped_reason: str
    fitments_total: int
    fitments_changed: int
    fitments_excluded: int
    link_quality_changed: bool


class Command(BaseCommand):
    help = "Persist Auto_DB fitment quality/exclusion flags from fitment audit CSV (dry-run or apply)."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, default="GPL")
        parser.add_argument("--audit-csv", type=str, required=True)
        parser.add_argument("--only-trusted", action="store_true")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--export-csv", type=str, default="")

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        do_apply = bool(options.get("apply"))
        if dry_run == do_apply:
            raise CommandError("Specify exactly one mode: --dry-run or --apply.")

        only_trusted = bool(options.get("only_trusted"))
        input_path = Path(str(options.get("audit_csv") or "")).expanduser()
        export_path = Path(str(options.get("export_csv") or "")).expanduser() if options.get("export_csv") else None
        if not input_path.exists():
            raise CommandError(f"Audit CSV not found: {input_path}")

        rows = self._read_rows(input_path)
        product_ids = sorted({row["product_id"] for row in rows if row["product_id"]})
        products = Product.objects.filter(id__in=product_ids).select_related("brand", "category")
        products_by_id = {str(product.id): product for product in products}

        results: list[PersistRowResult] = []
        counters = {
            "audited_rows": len(rows),
            "processed_products": 0,
            "suspicious_products": 0,
            "clean_products": 0,
            "would_mark_fitments_excluded": 0,
            "would_mark_products_with_fitments_excluded": 0,
            "would_keep_public": 0,
            "fitments_total": 0,
            "fitments_changed": 0,
            "fitments_excluded_after": 0,
            "link_quality_changed": 0,
            "skipped_missing_product": 0,
            "skipped_not_trusted": 0,
            "skipped_no_article_key": 0,
            "skipped_no_fitments": 0,
            "skipped_manual_locked_fitments": 0,
            "failed": 0,
            "would_delete": 0,
            "UTR_calls": 0,
        }

        for row in rows:
            product_id = row["product_id"]
            article_key = row["autodb_article_key"]
            suspicious = row["suspicious"]
            suspicious_reason = row["suspicious_reason"]
            product = products_by_id.get(product_id)
            if product is None:
                counters["skipped_missing_product"] += 1
                results.append(PersistRowResult(product_id, article_key, suspicious, "missing_product", 0, 0, 0, False))
                continue
            if not article_key:
                counters["skipped_no_article_key"] += 1
                results.append(PersistRowResult(product_id, article_key, suspicious, "missing_article_key", 0, 0, 0, False))
                continue

            if only_trusted and not AutoDbProductLinkQuality.objects.filter(
                product=product,
                autodb_article_key=article_key,
                status=AutoDbProductLinkQuality.STATUS_TRUSTED,
            ).exists():
                counters["skipped_not_trusted"] += 1
                results.append(PersistRowResult(product_id, article_key, suspicious, "not_trusted", 0, 0, 0, False))
                continue

            fitments = list(
                ProductFitment.objects.filter(
                    product=product,
                    source=ProductFitment.SOURCE_AUTODB_PRO,
                    autodb_article_key=article_key,
                ).order_by("id")
            )
            if not fitments:
                counters["skipped_no_fitments"] += 1
                results.append(PersistRowResult(product_id, article_key, suspicious, "no_fitments", 0, 0, 0, False))
                continue

            counters["processed_products"] += 1
            if suspicious:
                counters["suspicious_products"] += 1
            else:
                counters["clean_products"] += 1

            target_status = (
                ProductFitment.QUALITY_STATUS_SUSPICIOUS if suspicious else ProductFitment.QUALITY_STATUS_TRUSTED
            )
            target_excluded = bool(suspicious)
            target_reason = suspicious_reason if suspicious else ""

            changed = 0
            excluded_after = 0
            manual_locked = 0
            for fitment in fitments:
                if fitment.manual_locked:
                    manual_locked += 1
                    continue
                has_changes = False
                if str(fitment.quality_status or "") != target_status:
                    fitment.quality_status = target_status
                    has_changes = True
                if str(fitment.quality_reason or "") != target_reason:
                    fitment.quality_reason = target_reason
                    has_changes = True
                if bool(fitment.excluded_from_public_filtering) != target_excluded:
                    fitment.excluded_from_public_filtering = target_excluded
                    has_changes = True
                if has_changes:
                    changed += 1
                    if do_apply:
                        fitment.save(
                            update_fields=(
                                "quality_status",
                                "quality_reason",
                                "excluded_from_public_filtering",
                                "updated_at",
                            )
                        )
                if target_excluded:
                    excluded_after += 1

            link_quality_changed = False
            if suspicious:
                link_quality = (
                    AutoDbProductLinkQuality.objects.filter(product=product, autodb_article_key=article_key)
                    .order_by("-checked_at", "-updated_at")
                    .first()
                )
                if link_quality is not None and not link_quality.manually_confirmed:
                    desired_status = AutoDbProductLinkQuality.STATUS_SUSPICIOUS
                    desired_reason = target_reason
                    if str(link_quality.status or "") != desired_status or str(link_quality.reason or "") != desired_reason:
                        link_quality_changed = True
                        if do_apply:
                            link_quality.status = desired_status
                            link_quality.reason = desired_reason
                            link_quality.save(update_fields=("status", "reason", "updated_at"))

            counters["fitments_total"] += len(fitments)
            counters["fitments_changed"] += changed
            counters["fitments_excluded_after"] += excluded_after
            counters["skipped_manual_locked_fitments"] += manual_locked
            if target_excluded and excluded_after > 0:
                counters["would_mark_products_with_fitments_excluded"] += 1
                counters["would_mark_fitments_excluded"] += excluded_after
            if not target_excluded:
                counters["would_keep_public"] += 1
            if link_quality_changed:
                counters["link_quality_changed"] += 1

            results.append(
                PersistRowResult(
                    product_id=product_id,
                    article_key=article_key,
                    suspicious=suspicious,
                    skipped_reason="",
                    fitments_total=len(fitments),
                    fitments_changed=changed,
                    fitments_excluded=excluded_after,
                    link_quality_changed=link_quality_changed,
                )
            )

        if export_path is not None:
            export_path.parent.mkdir(parents=True, exist_ok=True)
            with export_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(
                    [
                        "product_id",
                        "article_key",
                        "suspicious",
                        "skipped_reason",
                        "fitments_total",
                        "fitments_changed",
                        "fitments_excluded",
                        "link_quality_changed",
                    ]
                )
                for item in results:
                    writer.writerow(
                        [
                            item.product_id,
                            item.article_key,
                            "1" if item.suspicious else "0",
                            item.skipped_reason,
                            item.fitments_total,
                            item.fitments_changed,
                            item.fitments_excluded,
                            "1" if item.link_quality_changed else "0",
                        ]
                    )

        mode = "dry-run" if dry_run else "apply"
        self.stdout.write(f"persist_autodb_fitment_quality {mode} summary:")
        for key in (
            "audited_rows",
            "processed_products",
            "suspicious_products",
            "clean_products",
            "would_mark_fitments_excluded",
            "would_mark_products_with_fitments_excluded",
            "would_keep_public",
            "fitments_total",
            "fitments_changed",
            "fitments_excluded_after",
            "link_quality_changed",
            "skipped_missing_product",
            "skipped_not_trusted",
            "skipped_no_article_key",
            "skipped_no_fitments",
            "skipped_manual_locked_fitments",
            "failed",
            "would_delete",
            "UTR_calls",
        ):
            self.stdout.write(f"- {key}: {counters[key]}")
        self.stdout.write("- Product.name/category/photo changed: 0")
        self.stdout.write("- SupplierOffer/ProductPrice changed: 0")
        if export_path is not None:
            self.stdout.write(f"- export_csv: {export_path}")

    def _read_rows(self, path: Path) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                flags = {item.strip() for item in str(row.get("suspicious_flags") or "").split(",") if item.strip()}
                rows.append(
                    {
                        "product_id": str(row.get("product_id") or "").strip(),
                        "autodb_article_key": str(row.get("autodb_article_key") or "").strip(),
                        "suspicious": "suspicious_link" in flags,
                        "suspicious_reason": str(row.get("suspicious_reason") or "").strip(),
                    }
                )
        return rows
