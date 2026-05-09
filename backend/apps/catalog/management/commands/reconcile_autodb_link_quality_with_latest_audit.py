from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import AutoDbProductLinkQuality, Product


class Command(BaseCommand):
    help = "Reconcile existing linked product quality status with latest candidate audit decisions (no unlink)."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, required=True, help="Supplier code, e.g. GPL")
        parser.add_argument("--latest-candidates-csv", type=str, required=True, help="Latest audit candidates CSV")
        parser.add_argument("--dry-run", action="store_true", help="Preview only")
        parser.add_argument("--apply", action="store_true", help="Write quality status changes")
        parser.add_argument("--export-csv", type=str, required=True, help="Detailed output CSV")

    def handle(self, *args, **options):
        supplier_code = str(options.get("supplier") or "").strip().lower()
        candidates_path = Path(str(options.get("latest_candidates_csv") or "")).expanduser()
        export_path = Path(str(options.get("export_csv") or "")).expanduser()
        dry_run = bool(options.get("dry_run"))
        do_apply = bool(options.get("apply"))

        if not supplier_code:
            raise CommandError("Provide --supplier")
        if not candidates_path.exists():
            raise CommandError(f"Latest candidates CSV not found: {candidates_path}")
        if dry_run == do_apply:
            raise CommandError("Specify exactly one mode: --dry-run or --apply.")

        candidate_rows = list(csv.DictReader(candidates_path.open(encoding="utf-8")))
        candidate_by_product: dict[str, dict[str, str]] = {}
        for row in candidate_rows:
            product_id = str(row.get("product_id") or "").strip()
            if product_id and product_id not in candidate_by_product:
                candidate_by_product[product_id] = row

        products = list(
            Product.objects.filter(supplier_offers__supplier__code=supplier_code)
            .exclude(autodb_article_key="")
            .distinct()
            .order_by("id")
            .only("id", "autodb_article_key", "autodb_supplier_id", "autodb_article_number")
        )

        quality_rows = list(
            AutoDbProductLinkQuality.objects.filter(product_id__in=[str(item.id) for item in products])
            .order_by("product_id", "-checked_at", "-updated_at", "-id")
            .only(
                "id",
                "product_id",
                "autodb_article_key",
                "autodb_supplier_id",
                "autodb_article_number",
                "status",
                "reason",
                "evidence",
            )
        )
        quality_by_product_key: dict[tuple[str, str], AutoDbProductLinkQuality] = {}
        for row in quality_rows:
            key = str(row.autodb_article_key or "").strip()
            pid = str(row.product_id)
            if key and (pid, key) not in quality_by_product_key:
                quality_by_product_key[(pid, key)] = row

        counters = {
            "linked_products_checked": 0,
            "linked_not_safe_rows": 0,
            "would_mark_needs_review": 0,
            "marked_needs_review": 0,
            "already_needs_review": 0,
            "would_unlink": 0,
            "skipped_safe": 0,
            "skipped_missing_in_csv": 0,
            "failed": 0,
            "would_change_product_name": 0,
            "would_change_product_category": 0,
            "would_change_product_image": 0,
            "would_change_price_stock": 0,
        }
        rows_out: list[dict[str, str]] = []

        for product in products:
            counters["linked_products_checked"] += 1
            pid = str(product.id)
            key = str(product.autodb_article_key or "").strip()
            supplier_id = getattr(product, "autodb_supplier_id", None)
            article_number = str(getattr(product, "autodb_article_number", "") or "").strip()
            latest = candidate_by_product.get(pid)

            if latest is None:
                counters["skipped_missing_in_csv"] += 1
                rows_out.append(
                    {
                        "product_id": pid,
                        "autodb_article_key": key,
                        "autodb_supplier_id": str(supplier_id or ""),
                        "autodb_article_number": article_number,
                        "latest_audit_decision": "",
                        "latest_audit_reason": "",
                        "current_quality_status": "",
                        "current_quality_reason": "",
                        "action": "skip_missing_from_csv",
                        "reason": "missing_in_latest_candidates_csv",
                    }
                )
                continue

            latest_decision = str(latest.get("decision") or "").strip()
            latest_reason = str(latest.get("reason") or "").strip()
            current_quality = quality_by_product_key.get((pid, key))
            current_status = str(getattr(current_quality, "status", "") or "").strip()
            current_reason = str(getattr(current_quality, "reason", "") or "").strip()

            if latest_decision == "safe_link_candidate":
                counters["skipped_safe"] += 1
                rows_out.append(
                    {
                        "product_id": pid,
                        "autodb_article_key": key,
                        "autodb_supplier_id": str(supplier_id or ""),
                        "autodb_article_number": article_number,
                        "latest_audit_decision": latest_decision,
                        "latest_audit_reason": latest_reason,
                        "current_quality_status": current_status,
                        "current_quality_reason": current_reason,
                        "action": "skip_safe",
                        "reason": "safe_in_latest_audit",
                    }
                )
                continue

            counters["linked_not_safe_rows"] += 1
            target_status = AutoDbProductLinkQuality.STATUS_NEEDS_MANUAL_REVIEW
            target_reason = f"latest_audit_{latest_reason or 'not_safe'}"

            same_status = current_status == target_status
            same_reason = current_reason == target_reason
            if same_status and same_reason:
                counters["already_needs_review"] += 1
                rows_out.append(
                    {
                        "product_id": pid,
                        "autodb_article_key": key,
                        "autodb_supplier_id": str(supplier_id or ""),
                        "autodb_article_number": article_number,
                        "latest_audit_decision": latest_decision,
                        "latest_audit_reason": latest_reason,
                        "current_quality_status": current_status,
                        "current_quality_reason": current_reason,
                        "action": "unchanged",
                        "reason": "already_needs_review",
                    }
                )
                continue

            counters["would_mark_needs_review"] += 1
            if do_apply:
                try:
                    self._apply_quality_update(
                        product=product,
                        autodb_article_key=key,
                        supplier_id=supplier_id,
                        article_number=article_number,
                        latest_decision=latest_decision,
                        latest_reason=latest_reason,
                    )
                    counters["marked_needs_review"] += 1
                    action = "marked_needs_review"
                except Exception:
                    counters["failed"] += 1
                    action = "failed"
            else:
                action = "would_mark_needs_review"

            rows_out.append(
                {
                    "product_id": pid,
                    "autodb_article_key": key,
                    "autodb_supplier_id": str(supplier_id or ""),
                    "autodb_article_number": article_number,
                    "latest_audit_decision": latest_decision,
                    "latest_audit_reason": latest_reason,
                    "current_quality_status": current_status,
                    "current_quality_reason": current_reason,
                    "action": action,
                    "reason": "latest_audit_not_safe_keep_link",
                }
            )

        export_path.parent.mkdir(parents=True, exist_ok=True)
        with export_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "product_id",
                    "autodb_article_key",
                    "autodb_supplier_id",
                    "autodb_article_number",
                    "latest_audit_decision",
                    "latest_audit_reason",
                    "current_quality_status",
                    "current_quality_reason",
                    "action",
                    "reason",
                ],
            )
            writer.writeheader()
            for row in rows_out:
                writer.writerow(row)

        mode = "dry-run" if dry_run else "apply"
        self.stdout.write(f"reconcile_autodb_link_quality_with_latest_audit {mode} summary:")
        for key in (
            "linked_products_checked",
            "linked_not_safe_rows",
            "would_mark_needs_review",
            "marked_needs_review",
            "already_needs_review",
            "would_unlink",
            "skipped_safe",
            "skipped_missing_in_csv",
            "failed",
            "would_change_product_name",
            "would_change_product_category",
            "would_change_product_image",
            "would_change_price_stock",
        ):
            self.stdout.write(f"- {key}: {counters[key]}")
        self.stdout.write("- UTR calls=0")
        self.stdout.write(f"- export_csv: {export_path}")

    @transaction.atomic
    def _apply_quality_update(
        self,
        *,
        product: Product,
        autodb_article_key: str,
        supplier_id: int | None,
        article_number: str,
        latest_decision: str,
        latest_reason: str,
    ) -> None:
        if not autodb_article_key:
            return

        reason = f"latest_audit_{latest_reason or 'not_safe'}"
        evidence = {
            "source": "reconcile_autodb_link_quality_with_latest_audit",
            "latest_audit_decision": latest_decision,
            "latest_audit_reason": latest_reason,
            "linked_fields_kept": True,
            "reconcile_mode": "quality_only",
        }
        quality, created = AutoDbProductLinkQuality.objects.get_or_create(
            product=product,
            autodb_article_key=autodb_article_key,
            defaults={
                "autodb_supplier_id": supplier_id,
                "autodb_article_number": article_number,
                "status": AutoDbProductLinkQuality.STATUS_NEEDS_MANUAL_REVIEW,
                "reason": reason,
                "evidence": evidence,
                "checked_at": timezone.now(),
            },
        )
        if created:
            return

        quality.autodb_supplier_id = supplier_id
        quality.autodb_article_number = article_number
        quality.status = AutoDbProductLinkQuality.STATUS_NEEDS_MANUAL_REVIEW
        quality.reason = reason
        quality.evidence = evidence
        quality.checked_at = timezone.now()
        quality.save(
            update_fields=[
                "autodb_supplier_id",
                "autodb_article_number",
                "status",
                "reason",
                "evidence",
                "checked_at",
                "updated_at",
            ]
        )
