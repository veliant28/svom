from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.catalog.models import AutoDbProductLinkQuality, Product
from apps.catalog.services.product_sku import get_product_display_sku


class Command(BaseCommand):
    help = "Read-only diagnosis of Auto-DB link completeness/quality vs latest candidate audit CSV."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, required=True, help="Supplier code, e.g. GPL")
        parser.add_argument("--latest-candidates-csv", type=str, required=True, help="Latest audit candidates CSV")
        parser.add_argument("--export-csv", type=str, required=True, help="Detailed output CSV")
        parser.add_argument("--summary-csv", type=str, required=True, help="Summary output CSV")

    def handle(self, *args, **options):
        supplier_code = str(options.get("supplier") or "").strip().lower()
        candidates_path = Path(str(options.get("latest_candidates_csv") or "")).expanduser()
        export_path = Path(str(options.get("export_csv") or "")).expanduser()
        summary_path = Path(str(options.get("summary_csv") or "")).expanduser()

        if not supplier_code:
            raise CommandError("Provide --supplier")
        if not candidates_path.exists():
            raise CommandError(f"Latest candidates CSV not found: {candidates_path}")

        candidate_rows = list(csv.DictReader(candidates_path.open(encoding="utf-8")))
        candidate_by_product: dict[str, dict[str, str]] = {}
        candidate_dupe_counter: Counter[str] = Counter()
        for row in candidate_rows:
            product_id = str(row.get("product_id") or "").strip()
            if not product_id:
                continue
            candidate_dupe_counter[product_id] += 1
            if product_id not in candidate_by_product:
                candidate_by_product[product_id] = row

        products = list(
            Product.objects.filter(supplier_offers__supplier__code=supplier_code)
            .distinct()
            .order_by("id")
            .only(
                "id",
                "sku",
                "autodb_supplier_id",
                "autodb_article_number",
                "autodb_article_key",
                "name",
                "article",
                "display_brand_name",
            )
        )
        product_ids = [str(item.id) for item in products]

        quality_rows = list(
            AutoDbProductLinkQuality.objects.filter(product_id__in=product_ids)
            .order_by("product_id", "-checked_at", "-updated_at", "-id")
            .only(
                "id",
                "product_id",
                "autodb_article_key",
                "autodb_supplier_id",
                "autodb_article_number",
                "status",
                "reason",
                "checked_at",
            )
        )
        quality_by_product: dict[str, list[AutoDbProductLinkQuality]] = defaultdict(list)
        quality_by_product_key: dict[tuple[str, str], AutoDbProductLinkQuality] = {}
        for row in quality_rows:
            pid = str(row.product_id)
            key = str(row.autodb_article_key or "").strip()
            quality_by_product[pid].append(row)
            if key and (pid, key) not in quality_by_product_key:
                quality_by_product_key[(pid, key)] = row

        key_counter = Counter(
            str(item.autodb_article_key or "").strip()
            for item in products
            if str(item.autodb_article_key or "").strip()
        )

        summary = Counter()
        rows_out: list[dict[str, str]] = []

        for product in products:
            pid = str(product.id)
            autodb_key = str(getattr(product, "autodb_article_key", "") or "").strip()
            supplier_id = getattr(product, "autodb_supplier_id", None)
            article_number = str(getattr(product, "autodb_article_number", "") or "").strip()
            has_key = bool(autodb_key)
            has_supplier_article = bool(supplier_id and article_number)
            canonical_key = f"{int(supplier_id)}:{article_number}" if has_supplier_article else ""
            complete = bool(has_key and has_supplier_article and autodb_key == canonical_key)
            has_any_link = bool(has_key or has_supplier_article)
            mismatched_key = bool(has_key and has_supplier_article and autodb_key != canonical_key)

            summary["products_total"] += 1
            if has_key:
                summary["linked_by_key"] += 1
            if has_supplier_article:
                summary["linked_by_supplier_article"] += 1
            if complete:
                summary["complete_link_fields"] += 1
            if has_any_link and not complete:
                summary["incomplete_link_fields"] += 1
            if mismatched_key:
                summary["mismatched_key_vs_supplier_article"] += 1

            q = quality_by_product_key.get((pid, autodb_key)) if autodb_key else None
            if q is None and quality_by_product.get(pid):
                q = quality_by_product[pid][0]
            quality_status = str(getattr(q, "status", "") or "").strip()
            quality_reason = str(getattr(q, "reason", "") or "").strip()

            if quality_status == AutoDbProductLinkQuality.STATUS_TRUSTED:
                summary["quality_trusted"] += 1
            elif quality_status == AutoDbProductLinkQuality.STATUS_NEEDS_MANUAL_REVIEW:
                summary["quality_needs_review"] += 1
            elif quality_status == AutoDbProductLinkQuality.STATUS_SUSPICIOUS:
                summary["quality_suspicious"] += 1

            latest = candidate_by_product.get(pid)
            latest_decision = str((latest or {}).get("decision") or "").strip()
            latest_reason = str((latest or {}).get("reason") or "").strip()
            latest_raw_brand = str((latest or {}).get("raw_brand") or "").strip()

            if has_key:
                if latest is None:
                    summary["linked_missing_from_latest_audit"] += 1
                elif latest_decision == "safe_link_candidate":
                    summary["linked_safe_in_latest_audit"] += 1
                else:
                    summary["linked_not_safe_in_latest_audit"] += 1

            recommended_action = "keep_trusted"
            if not complete and has_any_link:
                recommended_action = "fix_incomplete_link_fields"
            elif latest is None and has_key:
                recommended_action = "mark_needs_review"
            elif latest_decision == "semantic_conflict":
                recommended_action = "mark_suspicious"
            elif latest_decision and latest_decision != "safe_link_candidate":
                if quality_status == AutoDbProductLinkQuality.STATUS_TRUSTED:
                    recommended_action = "mark_needs_review"
                else:
                    recommended_action = "keep_trusted"

            should_export_row = bool(
                has_any_link
                and (
                    recommended_action != "keep_trusted"
                    or mismatched_key
                    or latest is None
                    or latest_decision != "safe_link_candidate"
                )
            )
            if should_export_row:
                rows_out.append(
                    {
                        "product_id": pid,
                        "display_sku": get_product_display_sku(product),
                        "raw_brand": str(getattr(product, "display_brand_name", "") or latest_raw_brand or ""),
                        "raw_td_article": str(getattr(product, "article", "") or ""),
                        "autodb_article_key": autodb_key,
                        "autodb_supplier_id": str(supplier_id or ""),
                        "autodb_article_number": article_number,
                        "latest_audit_decision": latest_decision,
                        "latest_audit_reason": latest_reason,
                        "link_quality_status": quality_status,
                        "link_quality_reason": quality_reason,
                        "hard_blocker_exists": "1" if latest_decision == "semantic_conflict" else "0",
                        "recommended_action": recommended_action,
                    }
                )

        duplicate_keys = [key for key, count in key_counter.items() if key and count > 1]
        summary["duplicate_autodb_key_rows"] = sum(key_counter[key] for key in duplicate_keys)
        summary["duplicate_autodb_key_unique"] = len(duplicate_keys)
        summary["safe_duplicate_product_ids"] = sum(1 for _, count in candidate_dupe_counter.items() if count > 1)

        export_path.parent.mkdir(parents=True, exist_ok=True)
        with export_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "product_id",
                    "display_sku",
                    "raw_brand",
                    "raw_td_article",
                    "autodb_article_key",
                    "autodb_supplier_id",
                    "autodb_article_number",
                    "latest_audit_decision",
                    "latest_audit_reason",
                    "link_quality_status",
                    "link_quality_reason",
                    "hard_blocker_exists",
                    "recommended_action",
                ],
            )
            writer.writeheader()
            for row in rows_out:
                writer.writerow(row)

        summary_rows = [
            {"metric": "products_total", "value": str(summary.get("products_total", 0))},
            {"metric": "linked_by_key", "value": str(summary.get("linked_by_key", 0))},
            {"metric": "linked_by_supplier_article", "value": str(summary.get("linked_by_supplier_article", 0))},
            {"metric": "complete_link_fields", "value": str(summary.get("complete_link_fields", 0))},
            {"metric": "incomplete_link_fields", "value": str(summary.get("incomplete_link_fields", 0))},
            {"metric": "quality_trusted", "value": str(summary.get("quality_trusted", 0))},
            {"metric": "quality_needs_review", "value": str(summary.get("quality_needs_review", 0))},
            {"metric": "quality_suspicious", "value": str(summary.get("quality_suspicious", 0))},
            {"metric": "linked_safe_in_latest_audit", "value": str(summary.get("linked_safe_in_latest_audit", 0))},
            {"metric": "linked_not_safe_in_latest_audit", "value": str(summary.get("linked_not_safe_in_latest_audit", 0))},
            {"metric": "linked_missing_from_latest_audit", "value": str(summary.get("linked_missing_from_latest_audit", 0))},
            {"metric": "mismatched_key_vs_supplier_article", "value": str(summary.get("mismatched_key_vs_supplier_article", 0))},
            {"metric": "duplicate_autodb_key_unique", "value": str(summary.get("duplicate_autodb_key_unique", 0))},
            {"metric": "duplicate_autodb_key_rows", "value": str(summary.get("duplicate_autodb_key_rows", 0))},
            {"metric": "safe_duplicate_product_ids", "value": str(summary.get("safe_duplicate_product_ids", 0))},
        ]
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        with summary_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=["metric", "value"])
            writer.writeheader()
            for row in summary_rows:
                writer.writerow(row)

        self.stdout.write("diagnose_autodb_link_state summary:")
        for row in summary_rows:
            self.stdout.write(f"- {row['metric']}: {row['value']}")
        self.stdout.write(f"- export_csv: {export_path}")
        self.stdout.write(f"- summary_csv: {summary_path}")
        self.stdout.write("- writes=0")
        self.stdout.write("- UTR calls=0")
