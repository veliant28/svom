from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_article
from apps.supplier_imports.gpl_article_resolver import GplArticleResolver


class Command(BaseCommand):
    help = "Backfill GPL SupplierRawOffer.article with resolved manufacturer article from raw_payload."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100, help="How many GPL rows to process.")
        parser.add_argument("--dry-run", action="store_true", help="Calculate updates without writing.")
        parser.add_argument("--all", action="store_true", help="Process all GPL rows (ignores --limit).")

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        process_all = bool(options.get("all"))
        limit = max(int(options.get("limit") or 100), 1)

        if process_all and dry_run and options.get("limit"):
            self.stdout.write("Dry-run with --all: processing all GPL offers.")
        if process_all and options.get("limit") and int(options.get("limit")) <= 0:
            raise CommandError("--limit must be positive")

        resolver = GplArticleResolver()
        qs = (
            SupplierRawOffer.objects.select_related("source", "supplier")
            .filter(Q(source__code__iexact="gpl") | Q(supplier__code__iexact="gpl"))
            .order_by("id")
        )
        if not process_all:
            qs = qs[:limit]

        total = 0
        updated = 0
        skipped = 0
        manual_required = 0
        source_counter: dict[str, int] = {}
        confidence_counter: dict[str, int] = {}

        self.stdout.write(f"GPL article backfill started dry_run={dry_run} all={process_all}")

        for offer in qs.iterator(chunk_size=500):
            total += 1
            payload = offer.raw_payload if isinstance(offer.raw_payload, dict) else {}
            resolution = resolver.resolve(
                raw_payload=payload,
                article=str(offer.article or ""),
                external_sku=str(offer.external_sku or ""),
            )
            source_counter[resolution.article_source] = source_counter.get(resolution.article_source, 0) + 1
            confidence_counter[resolution.article_confidence] = confidence_counter.get(resolution.article_confidence, 0) + 1

            if resolution.article_resolution_status != "resolved":
                manual_required += 1
                skipped += 1
                continue

            new_article = str(resolution.manufacturer_article or "").strip()
            new_normalized = normalize_article(new_article)
            if not new_article or not new_normalized:
                skipped += 1
                continue

            raw_meta = payload.get("gpl_article_resolution")
            if not isinstance(raw_meta, dict):
                raw_meta = {}
            raw_meta.update(
                {
                    "article_source": resolution.article_source,
                    "article_confidence": resolution.article_confidence,
                    "article_resolution_status": resolution.article_resolution_status,
                    "resolved_manufacturer_article": new_article,
                    "resolved_supplier_sku": resolution.supplier_sku,
                    "search_variants": list(resolution.search_variants),
                    "updated_at": timezone.now().isoformat(),
                }
            )
            payload["gpl_article_resolution"] = raw_meta

            needs_update = (
                str(offer.article or "").strip() != new_article
                or str(offer.normalized_article or "").strip() != new_normalized
                or str(offer.external_sku or "").strip() != str(resolution.supplier_sku or "").strip()
                or (offer.raw_payload or {}).get("gpl_article_resolution") != raw_meta
            )
            if not needs_update:
                skipped += 1
                continue

            if not dry_run:
                with transaction.atomic():
                    offer.article = new_article[:128]
                    offer.normalized_article = new_normalized[:128]
                    if resolution.supplier_sku:
                        offer.external_sku = str(resolution.supplier_sku)[:128]
                    offer.raw_payload = payload
                    offer.save(update_fields=("article", "normalized_article", "external_sku", "raw_payload", "updated_at"))
            updated += 1

        self.stdout.write("GPL article backfill summary:")
        self.stdout.write(f"- total rows: {total}")
        self.stdout.write(f"- updated rows: {updated}")
        self.stdout.write(f"- skipped rows: {skipped}")
        self.stdout.write(f"- manual_required rows: {manual_required}")
        self.stdout.write("- source distribution:")
        for key, value in sorted(source_counter.items(), key=lambda item: item[1], reverse=True):
            self.stdout.write(f"  - {key}: {value}")
        self.stdout.write("- confidence distribution:")
        for key, value in sorted(confidence_counter.items(), key=lambda item: item[1], reverse=True):
            self.stdout.write(f"  - {key}: {value}")
        self.stdout.write("- price/stock changed: 0")
        self.stdout.write("- UTR calls: 0")
