from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.autodb.services.local_db_readiness import wait_for_local_autodb_ready
from apps.autodb.services.unlinked_link_candidate_audit import (
    UnlinkedLinkCandidateAuditService,
    UnlinkedLinkCandidateRow,
    summarize_rows,
)
from apps.catalog.models import Product
from apps.catalog.services import get_product_display_brand_payload
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_brand


class Command(BaseCommand):
    help = "Read-only deep audit for unlinked GPL products and potential Auto_DB link candidates."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, required=True, help="Supplier/source code, e.g. GPL")
        parser.add_argument("--limit", type=int, default=500, help="Max unlinked products to inspect")
        parser.add_argument("--allow-remote", action="store_true", help="Enable read-only remote Auto_DB checks")
        parser.add_argument("--brands", type=str, default="", help='Optional CSV brand filter, e.g. "MITKA,CS SYSTEM"')
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV output path")
        parser.add_argument(
            "--export-manual-csv",
            type=str,
            default="",
            help="Optional CSV output path for manual mapping suggestions",
        )
        parser.add_argument(
            "--wait-for-autodb",
            type=int,
            default=0,
            help="Wait up to N seconds for local Auto_DB_Pro DB readiness",
        )

    def handle(self, *args, **options):
        supplier_code = str(options.get("supplier") or "").strip().lower()
        if not supplier_code:
            raise CommandError("Provide --supplier CODE")

        limit = max(int(options.get("limit") or 0), 0)
        allow_remote = bool(options.get("allow_remote"))
        export_csv = str(options.get("export_csv") or "").strip()
        export_manual_csv = str(options.get("export_manual_csv") or "").strip()
        wait_for_autodb = max(int(options.get("wait_for_autodb") or 0), 0)
        brand_filters = {
            normalize_brand(item.strip())
            for item in str(options.get("brands") or "").split(",")
            if normalize_brand(item.strip())
        }

        readiness = wait_for_local_autodb_ready(timeout_seconds=wait_for_autodb, interval_seconds=2.0)
        if not readiness.ready:
            raise CommandError(
                "Auto_DB_Pro local DB is not ready/recovering. Retry later. "
                f"host={readiness.host} port={readiness.port} database={readiness.database} "
                f"reason={readiness.reason} attempts={readiness.attempts} waited_seconds={readiness.waited_seconds}"
            )

        self.stdout.write(
            "Auto_DB unlinked link candidates audit started "
            f"supplier={supplier_code.upper()} limit={limit or 'none'} allow_remote={allow_remote} "
            f"brands={','.join(sorted(brand_filters)) or '-'}"
        )

        products = self._load_unlinked_products(supplier_code=supplier_code, limit=limit, brand_filters=brand_filters)
        raw_offer_map = self._load_latest_raw_offer_map(
            supplier_code=supplier_code,
            product_ids=[str(item.id) for item in products],
        )

        service = UnlinkedLinkCandidateAuditService()
        rows: list[UnlinkedLinkCandidateRow] = []

        for product in products:
            product_id = str(product.id)
            offer = raw_offer_map.get(product_id, {})
            payload = offer.get("raw_payload") if isinstance(offer, dict) else {}
            payload = payload if isinstance(payload, dict) else {}
            brand_payload = get_product_display_brand_payload(product)
            row = service.audit_offer(
                product_id=product_id,
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

        summary = summarize_rows(rows)

        counts_by_recommendation = Counter(item.recommendation for item in rows)
        counts_by_brand = Counter((item.raw_brand or item.display_brand or "-").strip() for item in rows)

        self.stdout.write("Audit summary:")
        self.stdout.write(f"- total_unlinked: {summary.total_unlinked}")
        self.stdout.write(f"- safe_auto_link_candidates: {summary.safe_auto_link_candidates}")
        self.stdout.write(f"- safe_article_variant_candidates: {summary.safe_article_variant_candidates}")
        self.stdout.write(f"- brand_alias_candidates: {summary.brand_alias_candidates}")
        self.stdout.write(f"- external_sku_candidates: {summary.external_sku_candidates}")
        self.stdout.write(f"- article_from_name_candidates: {summary.article_from_name_candidates}")
        self.stdout.write(f"- manual_mapping_needed: {summary.manual_mapping_needed}")
        self.stdout.write(f"- non_auto_or_supplier_only: {summary.non_auto_or_supplier_only}")
        self.stdout.write(f"- remote_not_found: {summary.remote_not_found}")
        self.stdout.write(f"- unsafe_ambiguous: {summary.unsafe_ambiguous}")
        self.stdout.write(f"- semantic_conflict: {summary.semantic_conflict}")

        self.stdout.write("- counts_by_recommendation:")
        for key, value in sorted(counts_by_recommendation.items(), key=lambda item: (-item[1], item[0])):
            self.stdout.write(f"  - {key}: {value}")

        self.stdout.write("- top_candidate_brands:")
        for key, value in counts_by_brand.most_common(20):
            self.stdout.write(f"  - {key}: {value}")

        self.stdout.write("Top 50 unlinked candidate field diagnostics:")
        for item in rows[:50]:
            self.stdout.write(
                f"- product_id={item.product_id} raw_offer_id={item.raw_offer_id or '-'} "
                f"raw_brand={item.raw_brand or '-'} raw_code={item.raw_code or '-'} raw_article={item.raw_article or '-'} "
                f"raw_article_td={item.raw_article_td or '-'} supplier_article_candidate={item.supplier_article_candidate or '-'} "
                f"manufacturer_article_candidate={item.manufacturer_article_candidate or '-'} "
                f"external_sku_candidate={item.external_sku_candidate or '-'} "
                f"article_from_name_candidate={item.article_from_name_candidate or '-'} "
                f"recommendation={item.recommendation} confidence={item.confidence:.2f} reason={item.reason}"
            )

        non_auto = [item for item in rows if item.recommendation == "non_auto_or_supplier_only"]
        needs_review = [item for item in rows if item.recommendation in {"manual_mapping_needed", "unsafe_ambiguous", "remote_not_found"}]

        self.stdout.write("Examples non_auto_or_supplier_only (top 20):")
        for item in non_auto[:20]:
            self.stdout.write(
                f"- product_id={item.product_id} raw_brand={item.raw_brand or '-'} "
                f"raw_name={item.raw_name or item.product_name or '-'} raw_category={item.raw_category or '-'} "
                f"raw_group={item.raw_group or '-'} reason={item.reason}"
            )

        self.stdout.write("Examples needs_manual_mapping/ambiguous (top 20):")
        for item in needs_review[:20]:
            self.stdout.write(
                f"- product_id={item.product_id} raw_brand={item.raw_brand or '-'} "
                f"supplier_article_candidate={item.supplier_article_candidate or '-'} "
                f"manufacturer_article_candidate={item.manufacturer_article_candidate or '-'} "
                f"recommendation={item.recommendation} reason={item.reason}"
            )

        if export_csv:
            self._export_csv(export_csv, rows)
            self.stdout.write(f"CSV export: {export_csv}")

        if export_manual_csv:
            self._export_manual_csv(export_manual_csv, rows)
            self.stdout.write(f"Manual mapping CSV export: {export_manual_csv}")

        self.stdout.write(f"- remote_checked: {'true' if allow_remote else 'false'}")
        self.stdout.write("- report_mode: read-only")
        self.stdout.write("- UTR calls=0")
        self.stdout.write("- price/stock changed=0")

    def _load_unlinked_products(self, *, supplier_code: str, limit: int, brand_filters: set[str]) -> list[Product]:
        qs = (
            Product.objects.select_related("brand")
            .filter(raw_supplier_offers__source__code=supplier_code)
            .filter(Q(autodb_supplier_id__isnull=True) | Q(autodb_article_key=""))
            .distinct()
            .order_by("id")
        )
        if brand_filters:
            qs = qs.filter(raw_supplier_offers__normalized_brand__in=brand_filters).distinct()
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

    def _export_csv(self, path: str, rows: list[UnlinkedLinkCandidateRow]) -> None:
        out_path = Path(path).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        headers = [
            "product_id",
            "raw_offer_id",
            "product_name",
            "display_brand",
            "brand_source",
            "raw_brand",
            "normalized_brand",
            "raw_code",
            "raw_category",
            "raw_article",
            "raw_name",
            "raw_description",
            "raw_group",
            "raw_article_td",
            "raw_image",
            "supplier_article_candidate",
            "manufacturer_article_candidate",
            "external_sku_candidate",
            "article_from_name_candidate",
            "article_from_description_candidate",
            "ean_candidate",
            "oe_candidate",
            "local_supplier_candidates_count",
            "remote_supplier_candidates_count",
            "exact_local_article_match",
            "exact_remote_article_match",
            "normalized_article_match",
            "variant_match",
            "article_numbers_table_match",
            "article_ean_match",
            "article_oe_match",
            "article_cross_match",
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
                writer.writerow(item.__dict__)

    def _export_manual_csv(self, path: str, rows: list[UnlinkedLinkCandidateRow]) -> None:
        out_path = Path(path).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        headers = [
            "raw_brand",
            "raw_article",
            "raw_name",
            "possible_supplier",
            "possible_article",
            "reason",
            "required_human_action",
        ]
        with out_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            for item in rows:
                if item.semantic_status == "conflict":
                    continue
                if item.recommendation not in {"manual_mapping_needed", "remote_not_found", "unsafe_ambiguous", "brand_alias_candidate"}:
                    continue
                possible_supplier = item.proposed_autodb_supplier_name or item.proposed_autodb_supplier_id
                possible_article = item.proposed_autodb_article_number or item.manufacturer_article_candidate or item.supplier_article_candidate
                raw_article = item.raw_article_td or item.raw_article or item.external_sku_candidate
                writer.writerow(
                    {
                        "raw_brand": item.raw_brand,
                        "raw_article": raw_article,
                        "raw_name": item.raw_name or item.product_name,
                        "possible_supplier": possible_supplier,
                        "possible_article": possible_article,
                        "reason": item.reason,
                        "required_human_action": "verify supplier+article mapping and create manual link rule",
                    }
                )
