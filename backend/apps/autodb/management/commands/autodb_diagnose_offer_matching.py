from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.autodb.services.article_number_normalizer import ArticleNumberNormalizer
from apps.autodb.services.raw_offer_enrichment import AutoDbRawOfferEnrichmentService, PairBucket, PairResolution
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_brand


@dataclass(frozen=True)
class OfferProbe:
    offer_id: str
    raw_brand: str
    normalized_brand: str
    raw_article: str
    normalized_article: str
    variants: tuple[str, ...]


class Command(BaseCommand):
    help = "Diagnose Auto_DB_Pro brand/article matching quality for SupplierRawOffer batch."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", required=True, help="Supplier/source code, e.g. GPL or UTR")
        parser.add_argument("--limit", type=int, default=100, help="Max raw offers")
        parser.add_argument("--sample-not-found", type=int, default=20, help="How many not-found samples to print")
        parser.add_argument("--sample-found", type=int, default=10, help="How many found samples to print")
        parser.add_argument("--allow-remote", action="store_true", help="Allow remote Auto_DB lookup fallback")
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV path for pair diagnostics")

    def handle(self, *args, **options):
        supplier_code = str(options.get("supplier") or "").strip()
        limit = max(int(options.get("limit") or 100), 1)
        sample_not_found = max(int(options.get("sample_not_found") or 20), 0)
        sample_found = max(int(options.get("sample_found") or 10), 0)
        allow_remote = bool(options.get("allow_remote")) and bool(getattr(settings, "AUTODB_PRO_REMOTE_ENABLED", False))
        export_csv = str(options.get("export_csv") or "").strip()

        normalizer = ArticleNumberNormalizer()
        service = AutoDbRawOfferEnrichmentService()

        qs = self._build_qs(supplier_code=supplier_code)[:limit]
        offers = list(qs)

        total_raw_offers = len(offers)
        top_brands = self._top_brands(offers)

        pair_to_probe: dict[tuple[str, str], OfferProbe] = {}
        valid_offers: list[SupplierRawOffer] = []
        reason_counts: dict[str, int] = {
            "brand_not_found": 0,
            "article_not_found_for_supplier": 0,
            "invalid_article": 0,
            "invalid_brand": 0,
            "missing_raw_fields": 0,
            "remote_disabled": 0,
            "remote_error": 0,
        }

        for offer in offers:
            raw_brand = str(offer.brand_name or "").strip()
            raw_article = str(offer.article or "").strip() or str(offer.external_sku or "").strip()
            normalized_brand = str(offer.normalized_brand or "").strip() or normalize_brand(raw_brand)
            article_norm = normalizer.normalize(raw_article or str(offer.normalized_article or ""))
            normalized_article = str(offer.normalized_article or "").strip() or article_norm.normalized

            if not raw_brand and not raw_article:
                reason_counts["missing_raw_fields"] += 1
                continue
            if not normalized_brand:
                reason_counts["invalid_brand"] += 1
                continue
            if not normalized_article:
                reason_counts["invalid_article"] += 1
                continue

            valid_offers.append(offer)
            key = (normalized_brand, normalized_article)
            if key not in pair_to_probe:
                pair_to_probe[key] = OfferProbe(
                    offer_id=str(offer.id),
                    raw_brand=raw_brand,
                    normalized_brand=normalized_brand,
                    raw_article=raw_article,
                    normalized_article=normalized_article,
                    variants=article_norm.search_variants,
                )

        buckets, _, failed_build = service.build_pair_buckets(offers=valid_offers)
        if failed_build:
            reason_counts["invalid_article"] += failed_build

        resolutions = self._resolve_buckets(
            service=service,
            buckets=buckets,
            allow_remote=allow_remote,
            batch_size=100,
        )

        found = 0
        not_found = 0
        failed = sum(
            reason_counts[item]
            for item in ["invalid_article", "invalid_brand", "missing_raw_fields"]
        )

        for item in resolutions:
            if item.article_key:
                found += 1
                continue
            not_found += 1
            reason = item.reason or "article_not_found_for_supplier"
            if item.source == "no_remote":
                reason = "remote_disabled"
            if any(str(w).startswith("remote_error:") for w in item.warnings):
                reason = "remote_error"
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

        self.stdout.write("Auto_DB_Pro offer matching diagnostics:")
        self.stdout.write(f"- supplier: {supplier_code}")
        self.stdout.write(f"- total raw offers: {total_raw_offers}")
        self.stdout.write(f"- unique brand/article pairs: {len(buckets)}")
        self.stdout.write(f"- unique brands: {len({item.normalized_brand for item in buckets})}")
        self.stdout.write(f"- found count: {found}")
        self.stdout.write(f"- not_found count: {not_found}")
        self.stdout.write(f"- failed count: {failed}")
        self.stdout.write("- reasons:")
        for key in [
            "brand_not_found",
            "article_not_found_for_supplier",
            "invalid_article",
            "invalid_brand",
            "missing_raw_fields",
            "remote_disabled",
            "remote_error",
        ]:
            self.stdout.write(f"  - {key}: {reason_counts.get(key, 0)}")

        self.stdout.write("Top raw brands:")
        for raw_brand, normalized_brand, count in top_brands[:30]:
            self.stdout.write(f"- {raw_brand or '-'} | normalized={normalized_brand or '-'} | count={count}")

        self.stdout.write("Supplier candidates by top brand:")
        brand_map = service.brand_matcher.resolve_many([item[1] for item in top_brands[:30]])
        for raw_brand, normalized_brand, count in top_brands[:30]:
            match = brand_map.get(normalized_brand)
            if not match or not match.candidates:
                self.stdout.write(f"- {raw_brand or '-'} -> no candidates")
                continue
            candidate = match.candidates[0]
            self.stdout.write(
                f"- {raw_brand or '-'} -> supplier_id={candidate.supplier_id} confidence={candidate.confidence:.2f} reason={candidate.reason}"
            )

        self.stdout.write("Article normalization examples:")
        for idx, probe in enumerate(pair_to_probe.values()):
            if idx >= 10:
                break
            self.stdout.write(
                f"- {probe.raw_article or '-'} => normalized={probe.normalized_article} variants={','.join(probe.variants[:6])}"
            )

        self.stdout.write("Sample not_found:")
        printed = 0
        for item in resolutions:
            if item.article_key:
                continue
            probe = pair_to_probe.get((item.bucket.normalized_brand, item.bucket.normalized_article))
            if not probe:
                continue
            reason = item.reason or "article_not_found_for_supplier"
            if item.source == "no_remote":
                reason = "remote_disabled"
            if any(str(w).startswith("remote_error:") for w in item.warnings):
                reason = "remote_error"
            candidate_preview = "; ".join(
                f"{cand.supplier_id}:{cand.confidence:.2f}:{cand.reason}" for cand in item.supplier_candidates[:3]
            )
            self.stdout.write(
                f"- offer_id={probe.offer_id} raw_brand={probe.raw_brand or '-'} normalized_brand={probe.normalized_brand} "
                f"raw_article={probe.raw_article or '-'} normalized_article={probe.normalized_article} "
                f"variants={','.join(probe.variants[:6])} reason={reason} supplier_candidates={candidate_preview or '-'}"
            )
            printed += 1
            if printed >= sample_not_found:
                break

        self.stdout.write("Sample found:")
        printed_found = 0
        for item in resolutions:
            if not item.article_key:
                continue
            probe = pair_to_probe.get((item.bucket.normalized_brand, item.bucket.normalized_article))
            if not probe:
                continue
            self.stdout.write(
                f"- offer_id={probe.offer_id} supplier_id={item.supplier_id} article_key={item.article_key} source={item.source}"
            )
            printed_found += 1
            if printed_found >= sample_found:
                break

        if export_csv:
            self._export_csv(export_csv=export_csv, resolutions=resolutions, probes=pair_to_probe)
            self.stdout.write(f"- csv_export: {export_csv}")

        self.stdout.write("- UTR calls: 0")

    def _resolve_buckets(
        self,
        *,
        service: AutoDbRawOfferEnrichmentService,
        buckets: list[PairBucket],
        allow_remote: bool,
        batch_size: int,
    ) -> list[PairResolution]:
        out: list[PairResolution] = []
        for idx in range(0, len(buckets), max(batch_size, 1)):
            chunk = buckets[idx : idx + max(batch_size, 1)]
            local = service._resolve_local_chunk(chunk)
            unresolved = [item for item in local if not item.article_key]
            if unresolved and allow_remote:
                try:
                    local = service._resolve_remote_chunk(local, persist_clone=False)
                except Exception as exc:  # noqa: BLE001
                    for item in unresolved:
                        item.source = "no_remote"
                        item.warnings.append(f"remote_error:{exc}")
            elif unresolved and not allow_remote:
                for item in unresolved:
                    item.source = "no_remote"
            out.extend(local)
        return out

    def _build_qs(self, *, supplier_code: str):
        code = supplier_code.strip().lower()
        return (
            SupplierRawOffer.objects.select_related("source", "supplier")
            .filter(Q(source__code__iexact=code) | Q(supplier__code__iexact=code))
            .order_by("id")
        )

    def _top_brands(self, offers: list[SupplierRawOffer]) -> list[tuple[str, str, int]]:
        counter: dict[tuple[str, str], int] = {}
        for offer in offers:
            raw = str(offer.brand_name or "").strip()
            normalized = str(offer.normalized_brand or "").strip() or normalize_brand(raw)
            key = (raw, normalized)
            counter[key] = counter.get(key, 0) + 1
        return sorted([(raw, normalized, count) for (raw, normalized), count in counter.items()], key=lambda item: item[2], reverse=True)

    def _export_csv(self, *, export_csv: str, resolutions: list[PairResolution], probes: dict[tuple[str, str], OfferProbe]) -> None:
        path = Path(export_csv).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "offer_id",
                    "raw_brand",
                    "normalized_brand",
                    "raw_article",
                    "normalized_article",
                    "supplier_id",
                    "article_key",
                    "source",
                    "reason",
                ],
            )
            writer.writeheader()
            for item in resolutions:
                probe = probes.get((item.bucket.normalized_brand, item.bucket.normalized_article))
                writer.writerow(
                    {
                        "offer_id": probe.offer_id if probe else "",
                        "raw_brand": probe.raw_brand if probe else "",
                        "normalized_brand": item.bucket.normalized_brand,
                        "raw_article": probe.raw_article if probe else "",
                        "normalized_article": item.bucket.normalized_article,
                        "supplier_id": item.supplier_id or "",
                        "article_key": item.article_key,
                        "source": item.source,
                        "reason": item.reason,
                    }
                )
