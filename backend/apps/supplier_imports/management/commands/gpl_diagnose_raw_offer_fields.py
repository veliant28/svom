from __future__ import annotations

import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.autodb.services.article_lookup import AutoDbArticleLookupService
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.gpl_article_resolver import GplArticleResolver


class Command(BaseCommand):
    help = "Diagnose GPL raw offer field mapping for manufacturer article vs GPL internal SKU."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100, help="How many GPL raw offers to inspect.")
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV export path.")
        parser.add_argument("--sample-not-found", type=int, default=50, help="How many not-found offers to probe with alternative candidates.")
        parser.add_argument("--allow-remote", action="store_true", help="Allow remote Auto-DB lookup fallback in diagnostics.")

    def handle(self, *args, **options):
        limit = max(int(options.get("limit") or 100), 1)
        export_csv = str(options.get("export_csv") or "").strip()
        sample_not_found = max(int(options.get("sample_not_found") or 50), 0)
        allow_remote = bool(options.get("allow_remote")) and bool(getattr(settings, "AUTODB_PRO_REMOTE_ENABLED", False))

        resolver = GplArticleResolver()
        lookup = AutoDbArticleLookupService()

        offers = list(
            SupplierRawOffer.objects.select_related("source", "supplier")
            .filter(Q(source__code__iexact="gpl") | Q(supplier__code__iexact="gpl"))
            .order_by("id")[:limit]
        )
        if not offers:
            self.stdout.write("No GPL offers found.")
            return

        keys_counter: dict[str, int] = {}
        rows: list[dict[str, str]] = []

        for offer in offers:
            payload = offer.raw_payload if isinstance(offer.raw_payload, dict) else {}
            for key in payload.keys():
                keys_counter[str(key)] = keys_counter.get(str(key), 0) + 1

            resolved = resolver.resolve(
                raw_payload=payload,
                article=str(offer.article or ""),
                external_sku=str(offer.external_sku or ""),
            )

            rows.append(
                {
                    "raw_offer_id": str(offer.id),
                    "article": str(offer.article or ""),
                    "normalized_article": str(offer.normalized_article or ""),
                    "brand_name": str(offer.brand_name or ""),
                    "normalized_brand": str(offer.normalized_brand or ""),
                    "product_name": str(offer.product_name or ""),
                    "supplier_sku": resolved.supplier_sku,
                    "manufacturer_article": resolved.manufacturer_article,
                    "article_source": resolved.article_source,
                    "article_confidence": resolved.article_confidence,
                    "article_resolution_status": resolved.article_resolution_status,
                    "payload_keys": ",".join(sorted(str(k) for k in payload.keys())),
                    "payload_article": resolved.candidates.get("article", ""),
                    "payload_manufacturer_article": resolved.candidates.get("manufacturer_article", ""),
                    "payload_vendor_code": resolved.candidates.get("vendor_code", ""),
                    "payload_ean": resolved.candidates.get("ean", ""),
                    "payload_oe": resolved.candidates.get("oe", ""),
                    "payload_cross": resolved.candidates.get("cross", ""),
                    "payload_image": resolved.candidates.get("image", ""),
                    "payload_price_rrc": resolved.candidates.get("price_rrc", ""),
                    "payload_price_opt2": resolved.candidates.get("price_opt2", ""),
                    "payload_price_opt4": resolved.candidates.get("price_opt4", ""),
                    "payload_price_opt10": resolved.candidates.get("price_opt10", ""),
                }
            )

        self.stdout.write("GPL raw offer field diagnostics:")
        self.stdout.write(f"- total offers: {len(offers)}")
        self.stdout.write(f"- unique raw_payload keys: {len(keys_counter)}")
        self.stdout.write("- top raw_payload keys:")
        for key, count in sorted(keys_counter.items(), key=lambda item: item[1], reverse=True)[:40]:
            self.stdout.write(f"  - {key}: {count}")

        self.stdout.write("- sample rows:")
        for row in rows[:20]:
            self.stdout.write(
                f"  - id={row['raw_offer_id']} brand={row['brand_name'] or '-'} article={row['article'] or '-'} "
                f"manufacturer_article={row['manufacturer_article'] or '-'} supplier_sku={row['supplier_sku'] or '-'} "
                f"source={row['article_source']} confidence={row['article_confidence']}"
            )

        self._diagnose_not_found_candidates(
            rows=rows,
            sample_not_found=sample_not_found,
            allow_remote=allow_remote,
            lookup=lookup,
        )

        if export_csv:
            self._export_csv(path=export_csv, rows=rows)
            self.stdout.write(f"- csv_export: {export_csv}")

        self.stdout.write("- UTR calls: 0")

    def _diagnose_not_found_candidates(
        self,
        *,
        rows: list[dict[str, str]],
        sample_not_found: int,
        allow_remote: bool,
        lookup: AutoDbArticleLookupService,
    ) -> None:
        if sample_not_found <= 0:
            return

        probes = rows[:sample_not_found]
        summary = {
            "found_by_supplierraw_article": 0,
            "found_by_supplier_sku": 0,
            "found_by_manufacturer_article": 0,
            "found_by_barcode_ean": 0,
            "found_by_oe_cross": 0,
            "still_not_found": 0,
            "lookup_error": 0,
        }
        details: list[str] = []

        for row in probes:
            brand = row["brand_name"] or row["normalized_brand"]
            resolved = False

            checks = [
                ("found_by_supplierraw_article", row.get("article", "")),
                ("found_by_supplier_sku", row.get("supplier_sku", "")),
                ("found_by_manufacturer_article", row.get("payload_manufacturer_article", "") or row.get("manufacturer_article", "")),
                ("found_by_barcode_ean", row.get("payload_ean", "")),
                ("found_by_oe_cross", row.get("payload_oe", "") or row.get("payload_cross", "")),
            ]

            for bucket, candidate in checks:
                value = str(candidate or "").strip()
                if not value:
                    continue
                try:
                    result = lookup.lookup(brand_name=brand, article=value, allow_remote=allow_remote)
                except Exception as exc:  # noqa: BLE001
                    summary["lookup_error"] += 1
                    details.append(
                        f"- offer_id={row['raw_offer_id']} lookup_error={exc} brand={brand} candidate={value}"
                    )
                    break
                if result.found:
                    summary[bucket] += 1
                    details.append(
                        f"- offer_id={row['raw_offer_id']} matched_by={bucket} brand={brand} candidate={value} key={result.article_key or '-'} source={result.article_source}"
                    )
                    resolved = True
                    break

            if not resolved:
                summary["still_not_found"] += 1
                details.append(
                    f"- offer_id={row['raw_offer_id']} not_found brand={brand} article={row.get('article','-')} "
                    f"manufacturer_article={row.get('manufacturer_article','-')} supplier_sku={row.get('supplier_sku','-')}"
                )

        self.stdout.write("- not_found candidate probe summary:")
        for key, value in summary.items():
            self.stdout.write(f"  - {key}: {value}")
        self.stdout.write("- not_found candidate probe samples:")
        for line in details[:20]:
            self.stdout.write(f"  {line}")

    def _export_csv(self, *, path: str, rows: list[dict[str, str]]) -> None:
        out = Path(path).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        if not rows:
            out.write_text("", encoding="utf-8")
            return

        fieldnames = list(rows[0].keys())
        with out.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
