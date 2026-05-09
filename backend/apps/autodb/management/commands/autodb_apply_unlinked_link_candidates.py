from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.autodb.services.local_db_readiness import wait_for_local_autodb_ready
from apps.autodb.services.unlinked_link_candidate_audit import UnlinkedLinkCandidateAuditService
from apps.catalog.models import Product
from apps.catalog.services import get_product_display_brand_payload
from apps.supplier_imports.models import SupplierRawOffer


class Command(BaseCommand):
    help = "Dry-run only: evaluate safe unlinked Auto_DB link candidates without writing Product links."

    SAFE_RECOMMENDATIONS = {"safe_auto_link_candidate", "safe_article_variant_candidate"}

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, required=True, help="Supplier/source code, e.g. GPL")
        parser.add_argument("--limit", type=int, default=500, help="Max unlinked products to inspect")
        parser.add_argument("--allow-remote", action="store_true", help="Enable read-only remote lookup in audit stage")
        parser.add_argument("--only-safe", action="store_true", help="Keep only safe recommendations")
        parser.add_argument("--min-confidence", type=float, default=0.95, help="Minimum confidence threshold")
        parser.add_argument("--dry-run", action="store_true", help="Required. This command is read-only in this stage")
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV output path")
        parser.add_argument("--wait-for-autodb", type=int, default=0, help="Wait up to N seconds for local Auto_DB readiness")

    def handle(self, *args, **options):
        supplier_code = str(options.get("supplier") or "").strip().lower()
        if not supplier_code:
            raise CommandError("Provide --supplier CODE")

        if not bool(options.get("dry_run")):
            raise CommandError("Safety guard: this stage allows dry-run only. Re-run with --dry-run.")

        limit = max(int(options.get("limit") or 0), 0)
        allow_remote = bool(options.get("allow_remote"))
        only_safe = bool(options.get("only_safe"))
        min_confidence = max(min(float(options.get("min_confidence") or 0.95), 1.0), 0.0)
        export_csv = str(options.get("export_csv") or "").strip()
        wait_for_autodb = max(int(options.get("wait_for_autodb") or 0), 0)

        readiness = wait_for_local_autodb_ready(timeout_seconds=wait_for_autodb, interval_seconds=2.0)
        if not readiness.ready:
            raise CommandError(
                "Auto_DB_Pro local DB is not ready/recovering. Retry later. "
                f"host={readiness.host} port={readiness.port} database={readiness.database} reason={readiness.reason}"
            )

        products = self._load_unlinked_products(supplier_code=supplier_code, limit=limit)
        raw_offer_map = self._load_latest_raw_offer_map(supplier_code=supplier_code, product_ids=[str(item.id) for item in products])
        service = UnlinkedLinkCandidateAuditService()

        rows = []
        for product in products:
            offer = raw_offer_map.get(str(product.id), {})
            payload = offer.get("raw_payload") if isinstance(offer, dict) else {}
            payload = payload if isinstance(payload, dict) else {}
            brand_payload = get_product_display_brand_payload(product)
            row = service.audit_offer(
                product_id=str(product.id),
                raw_offer_id=str(offer.get("id") or ""),
                product_name=str(product.name or ""),
                display_brand=str(brand_payload.display_brand or ""),
                brand_source=str(brand_payload.brand_source or ""),
                raw_brand=str(offer.get("brand_name") or ""),
                raw_payload=payload,
                raw_article=str(offer.get("article") or ""),
                external_sku=str(offer.get("external_sku") or ""),
                allow_remote=allow_remote,
                source_id=str(offer.get("source_id") or "") or None,
                supplier_id=str(offer.get("supplier_id") or "") or None,
            )
            rows.append(row)

        selected = [
            item
            for item in rows
            if item.confidence >= min_confidence
            and (
                (item.recommendation in self.SAFE_RECOMMENDATIONS)
                if only_safe
                else (item.recommendation in self.SAFE_RECOMMENDATIONS)
            )
        ]

        skipped_manual_review = sum(1 for item in rows if item.recommendation == "manual_mapping_needed")
        skipped_non_auto = sum(1 for item in rows if item.recommendation == "non_auto_or_supplier_only")
        skipped_semantic_conflict = sum(1 for item in rows if item.semantic_status == "conflict")
        skipped_ambiguous = sum(1 for item in rows if item.recommendation == "unsafe_ambiguous")

        self.stdout.write("Dry-run unlinked link apply summary:")
        self.stdout.write(f"- candidates_total: {len(rows)}")
        self.stdout.write(f"- selected_safe: {len(selected)}")
        self.stdout.write(f"- would_apply: {len(selected)}")
        self.stdout.write(f"- skipped_manual_review: {skipped_manual_review}")
        self.stdout.write(f"- skipped_non_auto: {skipped_non_auto}")
        self.stdout.write(f"- skipped_semantic_conflict: {skipped_semantic_conflict}")
        self.stdout.write(f"- skipped_ambiguous: {skipped_ambiguous}")
        self.stdout.write("- skipped_existing_conflict: 0")
        self.stdout.write("- failed: 0")

        self.stdout.write("Top safe candidates (max 30):")
        for item in selected[:30]:
            self.stdout.write(
                f"- product_id={item.product_id} raw_offer_id={item.raw_offer_id or '-'} "
                f"raw_brand={item.raw_brand or '-'} article_candidate={item.proposed_autodb_article_number or item.manufacturer_article_candidate or item.supplier_article_candidate or '-'} "
                f"proposed_supplier_id={item.proposed_autodb_supplier_id or '-'} proposed_supplier_name={item.proposed_autodb_supplier_name or '-'} "
                f"proposed_article_key={item.proposed_autodb_article_key or '-'} confidence={item.confidence:.2f} reason={item.reason}"
            )

        if export_csv:
            self._export_csv(export_csv, selected)
            self.stdout.write(f"CSV export: {export_csv}")

        self.stdout.write("- report_mode: dry-run-only")
        self.stdout.write("- link_writes: 0")
        self.stdout.write("- UTR calls=0")
        self.stdout.write("- price/stock changed=0")

    def _load_unlinked_products(self, *, supplier_code: str, limit: int) -> list[Product]:
        qs = (
            Product.objects.select_related("brand")
            .filter(raw_supplier_offers__source__code=supplier_code)
            .filter(Q(autodb_supplier_id__isnull=True) | Q(autodb_article_key=""))
            .distinct()
            .order_by("id")
        )
        if limit > 0:
            qs = qs[:limit]
        return list(qs)

    def _load_latest_raw_offer_map(self, *, supplier_code: str, product_ids: list[str]) -> dict[str, dict]:
        if not product_ids:
            return {}
        rows = (
            SupplierRawOffer.objects.filter(source__code=supplier_code, matched_product_id__in=product_ids)
            .order_by("matched_product_id", "-updated_at", "-id")
            .values(
                "id",
                "matched_product_id",
                "source_id",
                "supplier_id",
                "product_name",
                "brand_name",
                "article",
                "external_sku",
                "raw_payload",
            )
        )
        out: dict[str, dict] = {}
        for row in rows.iterator(chunk_size=500):
            key = str(row.get("matched_product_id") or "")
            if key and key not in out:
                out[key] = row
        return out

    def _export_csv(self, path: str, rows) -> None:
        out_path = Path(path).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        headers = [
            "product_id",
            "raw_offer_id",
            "raw_brand",
            "supplier_article_candidate",
            "manufacturer_article_candidate",
            "proposed_autodb_supplier_id",
            "proposed_autodb_supplier_name",
            "proposed_autodb_article_number",
            "proposed_autodb_article_key",
            "proposed_autodb_title",
            "confidence",
            "semantic_status",
            "recommendation",
            "reason",
        ]
        with out_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            for item in rows:
                writer.writerow(
                    {
                        "product_id": item.product_id,
                        "raw_offer_id": item.raw_offer_id,
                        "raw_brand": item.raw_brand,
                        "supplier_article_candidate": item.supplier_article_candidate,
                        "manufacturer_article_candidate": item.manufacturer_article_candidate,
                        "proposed_autodb_supplier_id": item.proposed_autodb_supplier_id,
                        "proposed_autodb_supplier_name": item.proposed_autodb_supplier_name,
                        "proposed_autodb_article_number": item.proposed_autodb_article_number,
                        "proposed_autodb_article_key": item.proposed_autodb_article_key,
                        "proposed_autodb_title": item.proposed_autodb_title,
                        "confidence": f"{item.confidence:.3f}",
                        "semantic_status": item.semantic_status,
                        "recommendation": item.recommendation,
                        "reason": item.reason,
                    }
                )
