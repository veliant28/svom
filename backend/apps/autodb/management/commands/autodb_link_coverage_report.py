from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.autodb.services.article_number_normalizer import ArticleNumberNormalizer
from apps.autodb.services.local_db_readiness import wait_for_local_autodb_ready
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.autodb.services.raw_offer_enrichment import AutoDbRawOfferEnrichmentService, PairBucket, PairResolution
from apps.autodb.services.remote_config import AutoDbRemoteConfigError, AutoDbRemoteConfigValidator
from apps.catalog.models import AutoDbProductLinkQuality, Product
from apps.compatibility.models import ProductFitment
from apps.supplier_imports.gpl_article_resolver import GplArticleResolver
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand


_STATUS_KEYS = (
    "linked_product",
    "linked_exact_local",
    "inherited_opportunity",
    "manual_mapping",
    "suspicious_link",
    "invalid_brand",
    "invalid_article",
    "missing_brand",
    "missing_article",
    "local_not_found_remote_not_checked",
    "remote_checked_not_found",
    "remote_error",
    "non_auto_or_supplier_only",
    "possible_non_auto_or_supplier_only",
    "needs_manual_mapping",
)


def _safe_json_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _payload_first(payload: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return ""


def _chunks(seq: list[Any], size: int) -> list[list[Any]]:
    step = max(size, 1)
    return [seq[idx : idx + step] for idx in range(0, len(seq), step)]


def _brand_hint_key(value: str) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE)


@dataclass
class PairStats:
    normalized_brand: str
    normalized_article: str
    source_ids: set[str] = field(default_factory=set)
    supplier_ids: set[str] = field(default_factory=set)
    source_codes: Counter[str] = field(default_factory=Counter)
    supplier_codes: Counter[str] = field(default_factory=Counter)
    raw_brand_counter: Counter[str] = field(default_factory=Counter)
    raw_article_counter: Counter[str] = field(default_factory=Counter)
    offer_count: int = 0
    matched_offer_count: int = 0
    matched_product_ids: set[str] = field(default_factory=set)
    manual_match_offers: int = 0
    suspicious_match_offers: int = 0
    invalid_brand_offers: int = 0
    invalid_article_offers: int = 0
    missing_brand_offers: int = 0
    missing_article_offers: int = 0
    sample_raw_offer_id: str = ""
    sample_raw_brand: str = ""
    sample_raw_article: str = ""
    sample_external_sku: str = ""
    sample_payload: dict[str, Any] = field(default_factory=dict)
    sample_variants: tuple[str, ...] = ()

    def supplier_code_label(self) -> str:
        if not self.supplier_codes:
            return "-"
        if len(self.supplier_codes) == 1:
            return next(iter(self.supplier_codes.keys()))
        return "MULTI"

    def source_code_label(self) -> str:
        if not self.source_codes:
            return "-"
        if len(self.source_codes) == 1:
            return next(iter(self.source_codes.keys()))
        return "MULTI"


@dataclass
class PairCoverageRow:
    pair_key: tuple[str, str]
    stats: PairStats
    resolution: PairResolution | None
    coverage_status: str
    reason: str
    confidence: float
    supplier_candidates: str
    article_variants: str
    matched_product_id: str
    matched_product_name: str
    current_autodb_article_key: str
    possible_next_step: str
    remote_checked: bool
    non_auto_label: str
    possible_non_auto: bool
    meaningful_exclusion: str = ""


@dataclass
class RemoteEvalStats:
    checked: bool = False
    queries: int = 0
    hits: int = 0
    checked_not_found: int = 0
    errors: int = 0
    not_checked: int = 0


class Command(BaseCommand):
    help = "Read-only Auto_DB_Pro link coverage report for SupplierRawOffer/Product diagnostics."

    EAN_KEYS = ("ean", "EAN", "barcode", "Barcode", "bar_code")
    OE_KEYS = ("oe", "oem", "oe_number", "OENbr", "oeNumber")
    CROSS_KEYS = ("cross", "cross_number", "crossNumber", "reference", "references", "analogs")

    INVALID_BRAND_HINTS = {
        _brand_hint_key("ТМК"): "ТМК",
        _brand_hint_key("Без бренду"): "Без бренду",
        _brand_hint_key("БелМаг"): "БелМаг",
        _brand_hint_key("Сімокс"): "Сімокс",
        _brand_hint_key("БРТ"): "БРТ",
    }

    OLD_ARTICLE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
        ("numeric_prefix", re.compile(r"^\d{3,}[A-Z0-9\-]*$", re.IGNORECASE)),
        ("url_like", re.compile(r"^https?://", re.IGNORECASE)),
        ("field_name_like", re.compile(r"^(article|код|sku|cid)$", re.IGNORECASE)),
    )
    NON_AUTO_BRAND_HINTS = {
        _brand_hint_key("CS SYSTEM"): "CS SYSTEM",
        _brand_hint_key("Mr.Build"): "Mr.Build",
        _brand_hint_key("NOVOABRASIVE"): "NOVOABRASIVE",
        _brand_hint_key("VIRA"): "VIRA",
        _brand_hint_key("K2"): "K2",
    }
    POSSIBLE_NON_AUTO_TOKENS = ("SYSTEM", "BUILD", "ABRASIVE", "PAINT", "ENAMEL", "ORGANIC", "NANO")

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, default="", help="Supplier/source code, e.g. GPL or UTR")
        parser.add_argument("--all", action="store_true", help="Run across all suppliers")
        parser.add_argument("--limit", type=int, default=0, help="Limit raw offers")
        parser.add_argument("--only-active-products", action="store_true", help="Include offers with active matched products only (unmatched offers stay included)")
        parser.add_argument("--only-in-stock", action="store_true", help="Include only offers with stock_qty > 0")
        parser.add_argument("--allow-remote", action="store_true", help="Allow remote Auto_DB Pro fallback for unresolved pairs")
        parser.add_argument("--sample-not-found", type=int, default=20, help="How many not_found pair samples to print")
        parser.add_argument("--sample-linked", type=int, default=20, help="How many linked pair samples to print")
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV path")
        parser.add_argument("--group-by", type=str, default="", choices=("", "brand", "reason", "source"), help="Print extra grouped breakdown")
        parser.add_argument("--wait-for-autodb", type=int, default=0, help="Wait up to N seconds for local Auto_DB_Pro readiness")
        parser.add_argument("--meaningful-only", action="store_true", help="Exclude invalid and non-auto/supplier-only buckets from coverage denominators")
        parser.add_argument("--remote-limit", type=int, default=0, help="Max unresolved pairs to remote-check when --allow-remote is used")
        parser.add_argument("--remote-top-brands", type=str, default="", help="Comma-separated brands to remote-check when --allow-remote is used")
        parser.add_argument("--remote-only-sample", type=int, default=0, help="Remote-check only top N unresolved pairs by offers")

    def handle(self, *args, **options):
        supplier_code = str(options.get("supplier") or "").strip()
        all_suppliers = bool(options.get("all"))
        limit = max(int(options.get("limit") or 0), 0)
        only_active_products = bool(options.get("only_active_products"))
        only_in_stock = bool(options.get("only_in_stock"))
        allow_remote_flag = bool(options.get("allow_remote"))
        sample_not_found = max(int(options.get("sample_not_found") or 20), 0)
        sample_linked = max(int(options.get("sample_linked") or 20), 0)
        export_csv = str(options.get("export_csv") or "").strip()
        group_by = str(options.get("group_by") or "").strip()
        wait_for_autodb = max(int(options.get("wait_for_autodb") or 0), 0)
        meaningful_only = bool(options.get("meaningful_only"))
        remote_limit = max(int(options.get("remote_limit") or 0), 0)
        remote_only_sample = max(int(options.get("remote_only_sample") or 0), 0)
        remote_top_brands_raw = str(options.get("remote_top_brands") or "").strip()
        remote_top_brands = {
            normalize_brand(item.strip())
            for item in remote_top_brands_raw.split(",")
            if item.strip()
        }

        if all_suppliers and supplier_code:
            raise CommandError("Use either --supplier or --all.")
        if not all_suppliers and not supplier_code:
            raise CommandError("Provide --supplier CODE or --all.")

        readiness = wait_for_local_autodb_ready(timeout_seconds=wait_for_autodb, interval_seconds=2.0)
        if not readiness.ready:
            raise CommandError(
                "Auto_DB_Pro local DB is not ready/recovering. "
                f"host={readiness.host} port={readiness.port} database={readiness.database} reason={readiness.reason}"
            )

        remote_enabled = bool(getattr(settings, "AUTODB_PRO_REMOTE_ENABLED", False))
        allow_remote = bool(allow_remote_flag and remote_enabled)
        remote_disabled_reason = ""
        if allow_remote_flag and not remote_enabled:
            remote_disabled_reason = "global_remote_disabled"
        if allow_remote:
            try:
                AutoDbRemoteConfigValidator.ensure_remote_ready(allow_remote=True)
            except AutoDbRemoteConfigError as exc:
                allow_remote = False
                remote_disabled_reason = f"remote_config_error:{exc}"

        self.stdout.write(
            "Auto_DB_Pro link coverage report started "
            f"scope={'ALL' if all_suppliers else supplier_code.upper()} limit={limit or 'none'} "
            f"only_active_products={only_active_products} only_in_stock={only_in_stock} "
            f"allow_remote={allow_remote} meaningful_only={meaningful_only}"
        )

        qs = self._build_queryset(
            supplier_code=supplier_code,
            all_suppliers=all_suppliers,
            only_active_products=only_active_products,
            only_in_stock=only_in_stock,
        )
        if limit > 0:
            qs = qs[:limit]

        pair_map, supplier_offer_totals, counters, gpl_diag = self._collect_pair_map(qs)

        if allow_remote and not (limit > 0 or remote_limit > 0 or remote_only_sample > 0 or remote_top_brands):
            raise CommandError(
                "Remote mode safety: pass --limit or --remote-limit or --remote-only-sample or --remote-top-brands with --allow-remote."
            )

        pair_rows, remote_stats = self._build_pair_rows(
            pair_map=pair_map,
            allow_remote=allow_remote,
            remote_disabled_reason=remote_disabled_reason,
            remote_limit=remote_limit,
            remote_top_brands=remote_top_brands,
            remote_only_sample=remote_only_sample,
        )
        pair_rows, meaningful_meta = self._apply_meaningful_filter(pair_rows=pair_rows, meaningful_only=meaningful_only)

        self._print_general_summary(
            counters=counters,
            pair_rows=pair_rows,
            supplier_offer_totals=supplier_offer_totals,
            meaningful_meta=meaningful_meta,
        )

        self._print_breakdown(pair_rows=pair_rows, remote_disabled_reason=remote_disabled_reason, remote_stats=remote_stats)
        self._print_supplier_breakdown(pair_rows=pair_rows, supplier_offer_totals=supplier_offer_totals)
        self._print_top_unlinked_brands(pair_rows=pair_rows, top_n=50)
        self._print_top_unlinked_articles(pair_rows=pair_rows, top_n=50)
        self._print_invalid_brand_breakdown(pair_rows=pair_rows)

        if supplier_code.lower() == "gpl" or all_suppliers:
            self._print_gpl_diagnostics(gpl_diag=gpl_diag)

        inherited = self._compute_inherited_opportunities(pair_rows=pair_rows)
        self._print_inherited(inherited)

        ean_oe_cross = self._compute_ean_oe_cross_opportunities(
            pair_rows=pair_rows,
            allow_remote=allow_remote,
        )
        self._print_ean_oe_cross(ean_oe_cross)

        suspicious = self._compute_suspicious_links(pair_rows=pair_rows)
        self._print_suspicious(suspicious)
        self._print_remote_summary(remote_stats=remote_stats)

        if group_by:
            self._print_grouped(pair_rows=pair_rows, key=group_by)

        self._print_samples(pair_rows=pair_rows, sample_not_found=sample_not_found, sample_linked=sample_linked)

        if export_csv:
            self._export_csv(path=export_csv, pair_rows=pair_rows)
            self.stdout.write(f"CSV export: {export_csv}")

        self.stdout.write("- report_mode: read-only (no Product/SupplierRawOffer writes)")
        self.stdout.write("- UTR calls: 0")
        self.stdout.write("- price/stock changed: 0")

    def _build_queryset(
        self,
        *,
        supplier_code: str,
        all_suppliers: bool,
        only_active_products: bool,
        only_in_stock: bool,
    ):
        qs = (
            SupplierRawOffer.objects.select_related("source", "supplier", "matched_product")
            .order_by("id")
            .values(
                "id",
                "source_id",
                "supplier_id",
                "source__code",
                "supplier__code",
                "brand_name",
                "normalized_brand",
                "article",
                "normalized_article",
                "external_sku",
                "stock_qty",
                "match_status",
                "match_reason",
                "matched_product_id",
                "matched_product__is_active",
                "raw_payload",
            )
        )
        if not all_suppliers:
            code = supplier_code.lower()
            qs = qs.filter(Q(source__code__iexact=code) | Q(supplier__code__iexact=code))
        if only_in_stock:
            qs = qs.filter(stock_qty__gt=0)
        if only_active_products:
            qs = qs.filter(Q(matched_product_id__isnull=True) | Q(matched_product__is_active=True))
        return qs

    def _collect_pair_map(self, qs):
        pair_map: dict[tuple[str, str], PairStats] = {}
        supplier_offer_totals: Counter[str] = Counter()
        normalizer = ArticleNumberNormalizer()
        gpl_resolver = GplArticleResolver()

        counters = {
            "total_raw_offers": 0,
            "total_offers_with_matched_product": 0,
            "missing_brand_offers": 0,
            "missing_article_offers": 0,
            "invalid_brand_offers": 0,
            "invalid_article_offers": 0,
        }

        gpl_diag = {
            "total_gpl_offers": 0,
            "article_eq_article_td": 0,
            "external_sku_eq_code": 0,
            "article_old_internal": 0,
            "old_pattern_counter": Counter(),
        }

        for row in qs.iterator(chunk_size=2000):
            counters["total_raw_offers"] += 1
            raw_brand = str(row.get("brand_name") or "").strip()
            raw_article = str(row.get("article") or "").strip()
            external_sku = str(row.get("external_sku") or "").strip()
            payload = _safe_json_dict(row.get("raw_payload"))

            source_code = str(row.get("source__code") or "").strip().lower()
            supplier_code = str(row.get("supplier__code") or "").strip().lower()
            report_supplier = supplier_code or source_code or "-"
            supplier_offer_totals[report_supplier] += 1

            is_gpl = source_code == "gpl" or supplier_code == "gpl"
            article_candidate = raw_article or external_sku
            if is_gpl:
                gpl_diag["total_gpl_offers"] += 1
                resolution = gpl_resolver.resolve(raw_payload=payload, article=raw_article, external_sku=external_sku)
                article_candidate = str(resolution.manufacturer_article or article_candidate).strip()

                article_td = _payload_first(payload, ("Артикул ТД", "manufacturer_article", "producer_article"))
                code_value = _payload_first(payload, ("Код", "cid", "supplier_sku", "external_sku"))
                if article_td and raw_article and article_td == raw_article:
                    gpl_diag["article_eq_article_td"] += 1
                if code_value and external_sku and code_value == external_sku:
                    gpl_diag["external_sku_eq_code"] += 1
                pattern_name = self._classify_old_article_pattern(raw_article)
                if pattern_name:
                    gpl_diag["article_old_internal"] += 1
                    gpl_diag["old_pattern_counter"][pattern_name] += 1

            normalized_brand = str(row.get("normalized_brand") or "").strip() or normalize_brand(raw_brand)
            article_norm = normalizer.normalize(article_candidate)
            normalized_article = str(row.get("normalized_article") or "").strip() or article_norm.normalized

            missing_brand = not raw_brand
            missing_article = not (raw_article or external_sku)
            invalid_brand = not normalized_brand
            invalid_article = not normalized_article

            if missing_brand:
                counters["missing_brand_offers"] += 1
            if missing_article:
                counters["missing_article_offers"] += 1
            if invalid_brand:
                counters["invalid_brand_offers"] += 1
            if invalid_article:
                counters["invalid_article_offers"] += 1

            if row.get("matched_product_id"):
                counters["total_offers_with_matched_product"] += 1

            if invalid_brand or invalid_article:
                key = (
                    normalized_brand or f"__invalid_brand__:{normalize_brand(raw_brand) or '-'}",
                    normalized_article or f"__invalid_article__:{normalize_article(raw_article or external_sku) or '-'}",
                )
            else:
                key = (normalized_brand, normalized_article)

            stats = pair_map.get(key)
            if stats is None:
                stats = PairStats(
                    normalized_brand=key[0],
                    normalized_article=key[1],
                )
                pair_map[key] = stats

            stats.offer_count += 1
            stats.raw_brand_counter[raw_brand or "-"] += 1
            stats.raw_article_counter[(raw_article or external_sku) or "-"] += 1
            stats.source_codes[source_code or "-"] += 1
            stats.supplier_codes[report_supplier] += 1

            if row.get("source_id"):
                stats.source_ids.add(str(row["source_id"]))
            if row.get("supplier_id"):
                stats.supplier_ids.add(str(row["supplier_id"]))

            if row.get("matched_product_id"):
                stats.matched_offer_count += 1
                stats.matched_product_ids.add(str(row["matched_product_id"]))

            if str(row.get("match_status") or "") == SupplierRawOffer.MATCH_STATUS_MANUALLY_MATCHED:
                stats.manual_match_offers += 1
            if str(row.get("match_reason") or "") == SupplierRawOffer.MATCH_REASON_AMBIGUOUS:
                stats.suspicious_match_offers += 1

            if missing_brand:
                stats.missing_brand_offers += 1
            if missing_article:
                stats.missing_article_offers += 1
            if invalid_brand:
                stats.invalid_brand_offers += 1
            if invalid_article:
                stats.invalid_article_offers += 1

            if not stats.sample_raw_offer_id:
                stats.sample_raw_offer_id = str(row.get("id") or "")
                stats.sample_raw_brand = raw_brand
                stats.sample_raw_article = raw_article or external_sku
                stats.sample_external_sku = external_sku
                stats.sample_payload = payload
                stats.sample_variants = article_norm.search_variants or ((normalized_article,) if normalized_article else ())

        return pair_map, supplier_offer_totals, counters, gpl_diag

    def _build_pair_rows(
        self,
        *,
        pair_map: dict[tuple[str, str], PairStats],
        allow_remote: bool,
        remote_disabled_reason: str,
        remote_limit: int,
        remote_top_brands: set[str],
        remote_only_sample: int,
    ) -> tuple[list[PairCoverageRow], RemoteEvalStats]:
        service = AutoDbRawOfferEnrichmentService()
        remote_stats = RemoteEvalStats(checked=allow_remote)
        buckets: list[PairBucket] = []

        for key, stats in pair_map.items():
            source_id = next(iter(stats.source_ids)) if len(stats.source_ids) == 1 else None
            supplier_id = next(iter(stats.supplier_ids)) if len(stats.supplier_ids) == 1 else None
            bucket = PairBucket(
                normalized_brand=stats.normalized_brand,
                normalized_article=stats.normalized_article,
                sample_brand=stats.sample_raw_brand or stats.normalized_brand,
                sample_article=stats.sample_raw_article or stats.normalized_article,
                article_variants=stats.sample_variants or ((stats.normalized_article,) if stats.normalized_article else ()),
                source_id=source_id,
                supplier_id=supplier_id,
                offer_count=stats.offer_count,
                matched_product_ids=set(stats.matched_product_ids),
            )
            buckets.append(bucket)

        resolutions_by_key: dict[tuple[str, str], PairResolution] = {}
        remote_budget = remote_limit if remote_limit > 0 else None
        remote_sample_budget = remote_only_sample if remote_only_sample > 0 else None
        if buckets:
            for chunk in _chunks(buckets, 500):
                local = service._resolve_local_chunk(chunk)
                unresolved = [item for item in local if not item.article_key]

                unresolved_for_remote: list[PairResolution] = []
                if unresolved:
                    if allow_remote:
                        candidates = list(unresolved)
                        if remote_top_brands:
                            candidates = [item for item in candidates if item.bucket.normalized_brand in remote_top_brands]
                        candidates.sort(key=lambda item: item.bucket.offer_count, reverse=True)
                        if remote_sample_budget is not None:
                            candidates = candidates[:remote_sample_budget]
                            remote_sample_budget = max(remote_sample_budget - len(candidates), 0)
                        if remote_budget is not None:
                            candidates = candidates[:remote_budget]
                            remote_budget = max(remote_budget - len(candidates), 0)
                        unresolved_for_remote = candidates
                        unresolved_for_remote_keys = {
                            (item.bucket.normalized_brand, item.bucket.normalized_article) for item in unresolved_for_remote
                        }
                        for item in unresolved:
                            key = (item.bucket.normalized_brand, item.bucket.normalized_article)
                            if key not in unresolved_for_remote_keys:
                                item.source = "no_remote"
                                item.warnings.append("remote_not_checked")
                                remote_stats.not_checked += 1
                    else:
                        for item in unresolved:
                            item.source = "no_remote"
                            item.warnings.append("remote_not_checked")
                            if remote_disabled_reason:
                                item.warnings.append(remote_disabled_reason)
                            remote_stats.not_checked += 1

                if unresolved_for_remote:
                    remote_stats.queries += 1
                    try:
                        remote_chunk = service._resolve_remote_chunk(unresolved_for_remote, persist_clone=False)
                        remote_map = {
                            (item.bucket.normalized_brand, item.bucket.normalized_article): item for item in remote_chunk
                        }
                        for idx, item in enumerate(local):
                            key = (item.bucket.normalized_brand, item.bucket.normalized_article)
                            if key in remote_map:
                                remote_item = remote_map[key]
                                remote_item.warnings.append("remote_checked")
                                local[idx] = remote_item
                    except Exception as exc:  # noqa: BLE001
                        remote_stats.errors += len(unresolved_for_remote)
                        for item in unresolved_for_remote:
                            item.source = "no_remote"
                            item.warnings.append(f"remote_error:{exc}")
                            item.warnings.append("remote_checked")

                for item in local:
                    resolutions_by_key[(item.bucket.normalized_brand, item.bucket.normalized_article)] = item
                    if item.source == "remote" and item.article_key:
                        remote_stats.hits += item.bucket.offer_count
                    if ("remote_checked" in item.warnings) and (not item.article_key):
                        remote_stats.checked_not_found += item.bucket.offer_count

        all_product_ids = sorted({pid for stats in pair_map.values() for pid in stats.matched_product_ids})
        if all_product_ids:
            raw_product_map = Product.objects.in_bulk(all_product_ids)
            product_map = {str(key): value for key, value in raw_product_map.items()}
            suspicious_product_ids = {
                str(item)
                for item in AutoDbProductLinkQuality.objects.filter(
                    status=AutoDbProductLinkQuality.STATUS_SUSPICIOUS,
                    product_id__in=all_product_ids,
                ).values_list("product_id", flat=True)
            }
        else:
            product_map = {}
            suspicious_product_ids = set()

        rows: list[PairCoverageRow] = []
        for key, stats in pair_map.items():
            resolution = resolutions_by_key.get(key)
            row = self._to_pair_row(
                stats=stats,
                resolution=resolution,
                product_map=product_map,
                suspicious_product_ids=suspicious_product_ids,
            )
            rows.append(row)

        rows.sort(key=lambda item: item.stats.offer_count, reverse=True)
        return rows, remote_stats

    def _to_pair_row(
        self,
        *,
        stats: PairStats,
        resolution: PairResolution | None,
        product_map: dict[str, Product],
        suspicious_product_ids: set[str],
    ) -> PairCoverageRow:
        matched_products = [product_map[pid] for pid in sorted(stats.matched_product_ids) if pid in product_map]
        matched_product_id = str(matched_products[0].id) if matched_products else ""
        matched_product_name = str(matched_products[0].name) if matched_products else ""

        linked_product = next((item for item in matched_products if str(item.autodb_article_key or "").strip()), None)
        current_autodb_article_key = str(linked_product.autodb_article_key or "") if linked_product else ""

        coverage_status = "needs_manual_mapping"
        reason = "needs_manual_mapping"
        confidence = 0.0
        possible_next_step = "manual_review"
        remote_checked = bool(resolution and ("remote_checked" in resolution.warnings))
        non_auto_label = self._non_auto_brand_label(stats.sample_raw_brand)
        possible_non_auto = self._possible_non_auto_brand(stats.sample_raw_brand)

        if stats.missing_brand_offers:
            coverage_status = "missing_brand"
            reason = "missing_brand"
            possible_next_step = "fill_brand"
        elif stats.missing_article_offers:
            coverage_status = "missing_article"
            reason = "missing_article"
            possible_next_step = "fill_article"
        elif stats.invalid_brand_offers:
            coverage_status = "invalid_brand"
            reason = "invalid_brand"
            possible_next_step = "normalize_brand"
        elif stats.invalid_article_offers:
            coverage_status = "invalid_article"
            reason = "invalid_article"
            possible_next_step = "normalize_article"
        validation_reason = reason if reason in {"missing_brand", "missing_article", "invalid_brand", "invalid_article"} else ""

        if not validation_reason and non_auto_label:
            coverage_status = "non_auto_or_supplier_only"
            reason = "non_auto_or_supplier_only"
            possible_next_step = "ignore_or_manual_review"
        elif not validation_reason and possible_non_auto:
            coverage_status = "possible_non_auto_or_supplier_only"
            reason = "possible_non_auto_or_supplier_only"
            possible_next_step = "manual_review"
        non_auto_locked = coverage_status in {"non_auto_or_supplier_only", "possible_non_auto_or_supplier_only"}

        if resolution is not None:
            confidence = float(resolution.supplier_candidates[0].confidence) if resolution.supplier_candidates else 0.0
            if resolution.article_key and not non_auto_locked:
                coverage_status = "linked_product" if resolution.source == "remote" else "linked_exact_local"
                canonical_norm = normalize_article(str(resolution.canonical_article_number or ""))
                reason = "linked_product" if resolution.source == "remote" else "linked_exact_local"
                possible_next_step = "link_ready"
                if resolution.supplier_candidates and str(resolution.supplier_candidates[0].reason).startswith("alias"):
                    reason = "linked_product"
                elif canonical_norm == stats.normalized_article:
                    reason = "linked_exact_local" if resolution.source == "local" else "linked_product"
                elif canonical_norm in {normalize_article(v) for v in stats.sample_variants if str(v).strip()}:
                    reason = "linked_product"
            elif not validation_reason and not non_auto_locked:
                if any(str(item).startswith("remote_error:") for item in resolution.warnings):
                    coverage_status = "remote_error"
                    reason = "remote_error"
                    possible_next_step = "check_remote_connectivity"
                elif remote_checked:
                    coverage_status = "remote_checked_not_found"
                    reason = "remote_checked_not_found"
                    possible_next_step = "manual_review"
                elif resolution.source == "no_remote":
                    coverage_status = "local_not_found_remote_not_checked"
                    reason = "local_not_found_remote_not_checked"
                    possible_next_step = "run_with_allow_remote"
                elif resolution.reason == "brand_not_found":
                    coverage_status = "invalid_brand"
                    reason = "invalid_brand"
                    possible_next_step = "brand_alias_mapping"
                elif resolution.reason == "article_not_found_for_supplier":
                    coverage_status = "local_not_found_remote_not_checked"
                    reason = "local_not_found_remote_not_checked"
                    possible_next_step = "article_backfill_or_manual_mapping"
                else:
                    coverage_status = "needs_manual_mapping"
                    reason = "needs_manual_mapping"

        if coverage_status not in {"linked_exact_local", "linked_product"} and current_autodb_article_key and not (resolution and resolution.article_key):
            coverage_status = "inherited_opportunity"
            reason = "inherited_opportunity"
            possible_next_step = "inherit_from_matched_product"

        if stats.manual_match_offers > 0 and coverage_status in {"needs_manual_mapping", "local_not_found_remote_not_checked", "remote_checked_not_found"}:
            coverage_status = "manual_mapping"
            reason = "manual_mapping"
            possible_next_step = "review_manual_mapping"

        if matched_product_id and (matched_product_id in suspicious_product_ids) and current_autodb_article_key:
            coverage_status = "suspicious_link"
            reason = "suspicious_link"
            possible_next_step = "manual_review"

        supplier_candidates = ""
        if resolution is not None and resolution.supplier_candidates:
            supplier_candidates = "; ".join(
                f"{cand.supplier_id}:{cand.confidence:.2f}:{cand.reason}" for cand in resolution.supplier_candidates[:5]
            )

        variants = ",".join(stats.sample_variants[:8]) if stats.sample_variants else ""

        return PairCoverageRow(
            pair_key=(stats.normalized_brand, stats.normalized_article),
            stats=stats,
            resolution=resolution,
            coverage_status=coverage_status,
            reason=reason,
            confidence=confidence,
            supplier_candidates=supplier_candidates,
            article_variants=variants,
            matched_product_id=matched_product_id,
            matched_product_name=matched_product_name,
            current_autodb_article_key=current_autodb_article_key,
            possible_next_step=possible_next_step,
            remote_checked=remote_checked,
            non_auto_label=non_auto_label,
            possible_non_auto=possible_non_auto,
        )

    def _print_general_summary(
        self,
        *,
        counters: dict[str, int],
        pair_rows: list[PairCoverageRow],
        supplier_offer_totals: Counter[str],
        meaningful_meta: dict[str, int],
    ):
        total_raw = int(counters["total_raw_offers"])
        unique_pairs = len(pair_rows)
        offers_with_matched_product = int(counters["total_offers_with_matched_product"])

        matched_product_ids = {row.matched_product_id for row in pair_rows if row.matched_product_id}
        linked_products = {row.matched_product_id for row in pair_rows if row.current_autodb_article_key and row.matched_product_id}
        suspicious_products = {row.matched_product_id for row in pair_rows if row.coverage_status == "suspicious_link" and row.matched_product_id}
        trusted_linked_products = linked_products - suspicious_products

        linked_pairs = [row for row in pair_rows if row.coverage_status in {"linked_exact_local", "linked_product"}]
        linked_offer_count = sum(row.stats.offer_count for row in linked_pairs)
        inherited_offer_count = sum(row.stats.offer_count for row in pair_rows if row.coverage_status == "inherited_opportunity")
        offers_on_linked_product = sum(row.stats.offer_count for row in pair_rows if row.current_autodb_article_key)

        coverage_offer_level = (offers_on_linked_product / total_raw * 100.0) if total_raw else 0.0
        coverage_pairs = (len(linked_pairs) / unique_pairs * 100.0) if unique_pairs else 0.0
        coverage_matched_products = (len(linked_products) / len(matched_product_ids) * 100.0) if matched_product_ids else 0.0
        coverage_trusted_products = (len(trusted_linked_products) / len(matched_product_ids) * 100.0) if matched_product_ids else 0.0

        self.stdout.write("Coverage summary:")
        self.stdout.write(f"- total raw offers: {total_raw}")
        self.stdout.write(f"- total unique brand+article pairs: {unique_pairs}")
        self.stdout.write(f"- total products with matched_product (offers-level): {offers_with_matched_product}")
        self.stdout.write(f"- linked products: {len(linked_products)}")
        self.stdout.write(f"- unlinked products: {max(len(matched_product_ids) - len(linked_products), 0)}")
        self.stdout.write("Coverage split:")
        self.stdout.write(f"- offer-level coverage (offers on linked product): {offers_on_linked_product}/{total_raw} ({coverage_offer_level:.2f}%)")
        self.stdout.write(f"- offer-level exact/local linked offers: {linked_offer_count}")
        self.stdout.write(f"- offer-level inherited opportunities: {inherited_offer_count}")
        self.stdout.write(f"- unique-pair linked coverage %: {coverage_pairs:.2f}")
        self.stdout.write(f"- matched-product linked coverage %: {coverage_matched_products:.2f}")
        self.stdout.write(f"- trusted-product coverage % (linked - suspicious): {coverage_trusted_products:.2f}")
        self.stdout.write(f"- suppliers in scope: {len([k for k in supplier_offer_totals if k and k != '-'])}")
        if meaningful_meta:
            self.stdout.write("Meaningful-only filter:")
            self.stdout.write(f"- enabled: {bool(meaningful_meta.get('enabled'))}")
            self.stdout.write(f"- kept_pairs: {meaningful_meta.get('kept_pairs', 0)}")
            self.stdout.write(f"- excluded_invalid: {meaningful_meta.get('excluded_invalid', 0)}")
            self.stdout.write(f"- excluded_non_auto: {meaningful_meta.get('excluded_non_auto', 0)}")
            self.stdout.write(f"- excluded_possible_non_auto: {meaningful_meta.get('excluded_possible_non_auto', 0)}")

    def _print_breakdown(self, *, pair_rows: list[PairCoverageRow], remote_disabled_reason: str, remote_stats: RemoteEvalStats):
        breakdown = {key: 0 for key in _STATUS_KEYS}

        for row in pair_rows:
            if row.coverage_status in breakdown:
                breakdown[row.coverage_status] += row.stats.offer_count
            elif row.reason in breakdown:
                breakdown[row.reason] += row.stats.offer_count
            else:
                breakdown["needs_manual_mapping"] += row.stats.offer_count

        self.stdout.write("Breakdown by status:")
        for key in _STATUS_KEYS:
            self.stdout.write(f"- {key}: {breakdown.get(key, 0)}")
        if remote_disabled_reason:
            self.stdout.write(f"- remote_disabled_reason: {remote_disabled_reason}")
        self.stdout.write(f"- remote_checked={remote_stats.checked}")

    def _print_supplier_breakdown(self, *, pair_rows: list[PairCoverageRow], supplier_offer_totals: Counter[str]):
        per_supplier: dict[str, dict[str, Any]] = defaultdict(lambda: {
            "total_offers": 0,
            "unique_pairs": set(),
            "linked_offers": 0,
            "not_found": 0,
            "failed": 0,
        })

        for row in pair_rows:
            for supplier_code, count in row.stats.supplier_codes.items():
                item = per_supplier[supplier_code]
                item["total_offers"] += count
                item["unique_pairs"].add(row.pair_key)
                if row.coverage_status in {"linked_exact_local", "linked_product", "inherited_opportunity"}:
                    item["linked_offers"] += count
                if row.coverage_status in {"local_not_found_remote_not_checked", "remote_checked_not_found", "needs_manual_mapping", "remote_error"}:
                    item["not_found"] += count
                if row.coverage_status in {"invalid_brand", "invalid_article", "missing_brand", "missing_article"}:
                    item["failed"] += count

        self.stdout.write("Breakdown by suppliers:")
        for supplier_code, data in sorted(per_supplier.items(), key=lambda kv: kv[1]["total_offers"], reverse=True):
            total = int(data["total_offers"])
            linked = int(data["linked_offers"])
            coverage = (linked / total * 100.0) if total else 0.0
            self.stdout.write(
                f"- {supplier_code or '-'}: total_offers={total} unique_pairs={len(data['unique_pairs'])} "
                f"linked={linked} not_found={int(data['not_found'])} failed={int(data['failed'])} coverage={coverage:.2f}%"
            )

    def _print_top_unlinked_brands(self, *, pair_rows: list[PairCoverageRow], top_n: int):
        brand_rows: dict[tuple[str, str, str], dict[str, Any]] = {}
        for row in pair_rows:
            if row.coverage_status in {"linked_exact_local", "linked_product", "suspicious_link"}:
                continue
            raw_brand = row.stats.raw_brand_counter.most_common(1)[0][0] if row.stats.raw_brand_counter else "-"
            normalized_brand = row.stats.normalized_brand
            reason = row.reason
            key = (raw_brand, normalized_brand, reason)
            item = brand_rows.get(key)
            if item is None:
                item = {
                    "offers": 0,
                    "articles": set(),
                    "supplier_candidates": row.supplier_candidates,
                }
                brand_rows[key] = item
            item["offers"] += row.stats.offer_count
            item["articles"].add(row.stats.normalized_article)

        top = sorted(brand_rows.items(), key=lambda kv: kv[1]["offers"], reverse=True)[:top_n]
        self.stdout.write(f"Top unlinked brands (top {top_n}):")
        for (raw_brand, normalized_brand, reason), item in top:
            self.stdout.write(
                f"- raw_brand={raw_brand} normalized_brand={normalized_brand or '-'} offers={item['offers']} "
                f"unique_articles={len(item['articles'])} supplier_candidates={item['supplier_candidates'] or '-'} reason={reason}"
            )

    def _print_top_unlinked_articles(self, *, pair_rows: list[PairCoverageRow], top_n: int):
        candidates = [row for row in pair_rows if row.coverage_status not in {"linked_exact_local", "linked_product", "suspicious_link"}]
        top = sorted(candidates, key=lambda row: row.stats.offer_count, reverse=True)[:top_n]
        self.stdout.write(f"Top unlinked articles (top {top_n}):")
        for row in top:
            self.stdout.write(
                f"- supplier={row.stats.supplier_code_label()} raw_brand={row.stats.sample_raw_brand or '-'} "
                f"normalized_brand={row.stats.normalized_brand or '-'} raw_article={row.stats.sample_raw_article or '-'} "
                f"normalized_article={row.stats.normalized_article or '-'} candidates={row.supplier_candidates or '-'} "
                f"variants={row.article_variants or '-'} reason={row.reason} offers={row.stats.offer_count}"
            )

    def _print_invalid_brand_breakdown(self, *, pair_rows: list[PairCoverageRow]):
        bucket: dict[str, dict[str, Any]] = {}
        examples: dict[str, list[str]] = defaultdict(list)
        for row in pair_rows:
            if row.coverage_status not in {"invalid_brand", "missing_brand"}:
                continue
            raw = row.stats.sample_raw_brand or "-"
            label = self.INVALID_BRAND_HINTS.get(_brand_hint_key(raw), raw or "-")
            item = bucket.get(label)
            if item is None:
                item = {"offers": 0, "articles": set()}
                bucket[label] = item
            item["offers"] += row.stats.offer_count
            item["articles"].add(row.stats.normalized_article)
            if len(examples[label]) < 3:
                examples[label].append(f"{raw or '-'} / {row.stats.sample_raw_article or '-'}")

        self.stdout.write("Invalid brand breakdown:")
        ordered = sorted(bucket.items(), key=lambda kv: kv[1]["offers"], reverse=True)
        for label, item in ordered[:30]:
            recommendation = self._invalid_brand_recommendation(label)
            self.stdout.write(
                f"- {label}: offers={item['offers']} unique_articles={len(item['articles'])} "
                f"examples={'; '.join(examples[label])} recommendation={recommendation}"
            )

    def _print_gpl_diagnostics(self, *, gpl_diag: dict[str, Any]):
        total = int(gpl_diag["total_gpl_offers"])
        self.stdout.write("GPL-specific diagnostics:")
        self.stdout.write(f"- total_gpl_offers: {total}")
        self.stdout.write(f"- count where article == Артикул ТД: {int(gpl_diag['article_eq_article_td'])}")
        self.stdout.write(f"- count where external_sku == Код: {int(gpl_diag['external_sku_eq_code'])}")
        self.stdout.write(f"- count where article looks old/internal: {int(gpl_diag['article_old_internal'])}")
        self.stdout.write("- top old/bad article patterns:")
        for key, value in gpl_diag["old_pattern_counter"].most_common(10):
            self.stdout.write(f"  - {key}: {value}")
        need_backfill = bool(gpl_diag["article_old_internal"] or (total and gpl_diag["article_eq_article_td"] < total // 2))
        self.stdout.write(f"- gpl_backfill_article_fields_needed: {'yes' if need_backfill else 'no'}")

    def _compute_inherited_opportunities(self, *, pair_rows: list[PairCoverageRow]) -> dict[str, Any]:
        candidates = [row for row in pair_rows if row.coverage_status == "inherited_opportunity"]
        product_ids = {row.matched_product_id for row in candidates if row.matched_product_id}
        suspicious_ids = set(
            AutoDbProductLinkQuality.objects.filter(
                status=AutoDbProductLinkQuality.STATUS_SUSPICIOUS,
                product_id__in=product_ids,
            ).values_list("product_id", flat=True)
        )
        examples = []
        for row in candidates[:20]:
            examples.append(
                {
                    "supplier": row.stats.supplier_code_label(),
                    "raw_brand": row.stats.sample_raw_brand,
                    "raw_article": row.stats.sample_raw_article,
                    "matched_product_id": row.matched_product_id,
                    "autodb_article_key": row.current_autodb_article_key,
                    "offers": row.stats.offer_count,
                    "link_quality": "suspicious" if row.matched_product_id in suspicious_ids else "trusted",
                }
            )

        risk = "low"
        if len(candidates) >= 100:
            risk = "medium"
        if len(candidates) >= 1000:
            risk = "high"

        return {
            "count_pairs": len(candidates),
            "count_offers": sum(row.stats.offer_count for row in candidates),
            "count_products": len(product_ids),
            "examples": examples,
            "risk": risk,
        }

    def _print_inherited(self, inherited: dict[str, Any]):
        self.stdout.write("Inherited link opportunities:")
        self.stdout.write(f"- count offers: {inherited['count_offers']}")
        self.stdout.write(f"- count unique pairs: {inherited['count_pairs']}")
        self.stdout.write(f"- count products: {inherited['count_products']}")
        self.stdout.write(f"- risk level: {inherited['risk']}")
        for row in inherited["examples"][:20]:
            self.stdout.write(
                f"- supplier={row['supplier']} raw_brand={row['raw_brand'] or '-'} raw_article={row['raw_article'] or '-'} "
                f"matched_product={row['matched_product_id']} autodb_article_key={row['autodb_article_key']} "
                f"quality={row['link_quality']} offers={row['offers']}"
            )

    def _compute_ean_oe_cross_opportunities(self, *, pair_rows: list[PairCoverageRow], allow_remote: bool) -> dict[str, Any]:
        unlinked = [row for row in pair_rows if row.coverage_status not in {"linked_exact_local", "linked_product"}]
        offer_count = sum(row.stats.offer_count for row in unlinked)

        ean_values: set[str] = set()
        oe_values: set[str] = set()
        cross_values: set[str] = set()
        ean_offers = 0
        oe_offers = 0
        cross_offers = 0

        for row in unlinked:
            payload = row.stats.sample_payload
            ean = _payload_first(payload, self.EAN_KEYS)
            oe = _payload_first(payload, self.OE_KEYS)
            cross = _payload_first(payload, self.CROSS_KEYS)
            if ean:
                ean_offers += row.stats.offer_count
                ean_values.add(ean)
            if oe:
                oe_offers += row.stats.offer_count
                oe_values.add(oe)
            if cross:
                cross_offers += row.stats.offer_count
                cross_values.add(cross)

        storage = AutoDbRawCloneStorage()
        ean_hits = self._lookup_local_signal_hits(storage=storage, table="article_ean", values=ean_values, candidate_columns=("ean", "EAN", "barcode", "BarCode", "code"))
        oe_hits = self._lookup_local_signal_hits(storage=storage, table="article_oe", values=oe_values, candidate_columns=("oe", "oem", "number", "oe_number"))
        cross_hits = self._lookup_local_signal_hits(storage=storage, table="article_cross", values=cross_values, candidate_columns=("cross", "cross_number", "number", "reference"))

        return {
            "unlinked_offers": offer_count,
            "ean_offers": ean_offers,
            "oe_offers": oe_offers,
            "cross_offers": cross_offers,
            "ean_unique_values": len(ean_values),
            "oe_unique_values": len(oe_values),
            "cross_unique_values": len(cross_values),
            "ean_local_lookup_opportunities": ean_hits,
            "oe_local_lookup_opportunities": oe_hits,
            "cross_local_lookup_opportunities": cross_hits,
            "lookup_mode": "local-only" if not allow_remote else "local+remote-allowed",
        }

    def _lookup_local_signal_hits(
        self,
        *,
        storage: AutoDbRawCloneStorage,
        table: str,
        values: set[str],
        candidate_columns: tuple[str, ...],
    ) -> int:
        if not values:
            return 0
        local_columns = storage.get_local_columns(table)
        if not local_columns:
            return 0
        selected = next((name for name in candidate_columns if name.lower() in {item.lower() for item in local_columns}), "")
        if not selected:
            return 0
        hits: set[str] = set()
        for chunk in _chunks(sorted(values), 500):
            rows = storage.fetch_local_rows_in(table=table, column=selected, values=chunk, limit=100000, columns=[selected])
            for row in rows:
                value = str(row.get(selected) or "").strip()
                if value:
                    hits.add(value)
        return len(hits)

    def _print_ean_oe_cross(self, payload: dict[str, Any]):
        self.stdout.write("EAN/OE/Cross opportunities:")
        self.stdout.write(f"- unlinked offers: {payload['unlinked_offers']}")
        self.stdout.write(f"- unlinked offers with EAN: {payload['ean_offers']}")
        self.stdout.write(f"- unlinked offers with OE: {payload['oe_offers']}")
        self.stdout.write(f"- unlinked offers with cross/reference: {payload['cross_offers']}")
        self.stdout.write(f"- EAN unique values: {payload['ean_unique_values']}")
        self.stdout.write(f"- OE unique values: {payload['oe_unique_values']}")
        self.stdout.write(f"- Cross unique values: {payload['cross_unique_values']}")
        self.stdout.write(f"- local EAN lookup opportunities: {payload['ean_local_lookup_opportunities']}")
        self.stdout.write(f"- local OE lookup opportunities: {payload['oe_local_lookup_opportunities']}")
        self.stdout.write(f"- local Cross lookup opportunities: {payload['cross_local_lookup_opportunities']}")

    def _compute_suspicious_links(self, *, pair_rows: list[PairCoverageRow]) -> dict[str, Any]:
        product_ids = {row.matched_product_id for row in pair_rows if row.matched_product_id}
        suspicious_quality = (
            AutoDbProductLinkQuality.objects.filter(status=AutoDbProductLinkQuality.STATUS_SUSPICIOUS, product_id__in=product_ids)
            .values("product_id", "autodb_article_key", "reason")
        )
        suspicious_fitments = (
            ProductFitment.objects.filter(product_id__in=product_ids, excluded_from_public_filtering=True)
            .values("product_id", "autodb_article_key", "quality_status", "quality_reason")
        )

        suspicious_product_ids = {str(item["product_id"]) for item in suspicious_quality}
        offer_affected = sum(row.stats.offer_count for row in pair_rows if row.matched_product_id in suspicious_product_ids)
        examples = []
        for row in suspicious_quality[:10]:
            examples.append(
                f"quality product={row['product_id']} key={row['autodb_article_key']} reason={row['reason'] or '-'}"
            )
        for row in suspicious_fitments[:10]:
            examples.append(
                f"fitment product={row['product_id']} key={row['autodb_article_key'] or '-'} quality={row['quality_status'] or '-'} reason={row['quality_reason'] or '-'}"
            )

        return {
            "suspicious_products": len(suspicious_product_ids),
            "suspicious_offers_affected": offer_affected,
            "suspicious_quality_count": suspicious_quality.count(),
            "excluded_fitment_count": suspicious_fitments.count(),
            "total_suspicious": suspicious_quality.count() + suspicious_fitments.count(),
            "examples": examples[:20],
        }

    def _print_suspicious(self, suspicious: dict[str, Any]):
        self.stdout.write("Suspicious links:")
        self.stdout.write(f"- suspicious products: {suspicious['suspicious_products']}")
        self.stdout.write(f"- raw offers affected: {suspicious['suspicious_offers_affected']}")
        self.stdout.write(f"- AutoDbProductLinkQuality suspicious: {suspicious['suspicious_quality_count']}")
        self.stdout.write(f"- ProductFitment excluded_from_public_filtering: {suspicious['excluded_fitment_count']}")
        self.stdout.write(f"- suspicious total: {suspicious['total_suspicious']}")
        for line in suspicious["examples"][:10]:
            self.stdout.write(f"- {line}")

    def _print_grouped(self, *, pair_rows: list[PairCoverageRow], key: str):
        self.stdout.write(f"Grouped breakdown by {key}:")
        grouped: Counter[str] = Counter()
        for row in pair_rows:
            if key == "brand":
                label = row.stats.normalized_brand or "-"
            elif key == "reason":
                label = row.reason
            else:
                label = row.resolution.source if row.resolution else "none"
            grouped[label] += row.stats.offer_count
        for name, count in grouped.most_common(100):
            self.stdout.write(f"- {name}: {count}")

    def _print_samples(self, *, pair_rows: list[PairCoverageRow], sample_not_found: int, sample_linked: int):
        self.stdout.write("Sample unresolved:")
        printed = 0
        for row in pair_rows:
            if row.coverage_status in {"linked_exact_local", "linked_product"}:
                continue
            self.stdout.write(
                f"- offer_id={row.stats.sample_raw_offer_id} supplier={row.stats.supplier_code_label()} raw_brand={row.stats.sample_raw_brand or '-'} "
                f"raw_article={row.stats.sample_raw_article or '-'} normalized_brand={row.stats.normalized_brand or '-'} "
                f"normalized_article={row.stats.normalized_article or '-'} reason={row.reason} candidates={row.supplier_candidates or '-'}"
            )
            printed += 1
            if printed >= sample_not_found:
                break

        self.stdout.write("Sample linked:")
        printed = 0
        for row in pair_rows:
            if row.coverage_status not in {"linked_exact_local", "linked_product"}:
                continue
            supplier_id = row.resolution.supplier_id if row.resolution else "-"
            article_key = row.resolution.article_key if row.resolution else "-"
            self.stdout.write(
                f"- offer_id={row.stats.sample_raw_offer_id} supplier={row.stats.supplier_code_label()} "
                f"supplier_id={supplier_id} article_key={article_key} reason={row.reason}"
            )
            printed += 1
            if printed >= sample_linked:
                break

    def _export_csv(self, *, path: str, pair_rows: list[PairCoverageRow]):
        export_path = Path(path).expanduser()
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with export_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "supplier",
                    "raw_brand",
                    "normalized_brand",
                    "raw_article",
                    "normalized_article",
                    "product_id",
                    "product_name",
                    "matched_product",
                    "current_autodb_article_key",
                    "coverage_status",
                    "reason",
                    "supplier_candidates",
                    "article_variants",
                    "possible_next_step",
                    "confidence",
                    "sample_raw_offer_id",
                ],
            )
            writer.writeheader()
            for row in pair_rows:
                writer.writerow(
                    {
                        "supplier": row.stats.supplier_code_label(),
                        "raw_brand": row.stats.sample_raw_brand,
                        "normalized_brand": row.stats.normalized_brand,
                        "raw_article": row.stats.sample_raw_article,
                        "normalized_article": row.stats.normalized_article,
                        "product_id": row.matched_product_id,
                        "product_name": row.matched_product_name,
                        "matched_product": "yes" if row.matched_product_id else "no",
                        "current_autodb_article_key": row.current_autodb_article_key,
                        "coverage_status": row.coverage_status,
                        "reason": row.reason,
                        "supplier_candidates": row.supplier_candidates,
                        "article_variants": row.article_variants,
                        "possible_next_step": row.possible_next_step,
                        "confidence": f"{row.confidence:.2f}",
                        "sample_raw_offer_id": row.stats.sample_raw_offer_id,
                    }
                )

    def _apply_meaningful_filter(self, *, pair_rows: list[PairCoverageRow], meaningful_only: bool) -> tuple[list[PairCoverageRow], dict[str, int]]:
        meta = {
            "enabled": 1 if meaningful_only else 0,
            "kept_pairs": len(pair_rows),
            "excluded_invalid": 0,
            "excluded_non_auto": 0,
            "excluded_possible_non_auto": 0,
        }
        if not meaningful_only:
            return pair_rows, meta

        kept: list[PairCoverageRow] = []
        for row in pair_rows:
            exclusion = ""
            if row.coverage_status in {"invalid_brand", "invalid_article", "missing_brand", "missing_article"}:
                exclusion = "invalid_or_missing"
                meta["excluded_invalid"] += row.stats.offer_count
            elif row.coverage_status == "non_auto_or_supplier_only":
                exclusion = "non_auto_or_supplier_only"
                meta["excluded_non_auto"] += row.stats.offer_count
            elif row.coverage_status == "possible_non_auto_or_supplier_only":
                exclusion = "possible_non_auto_or_supplier_only"
                meta["excluded_possible_non_auto"] += row.stats.offer_count

            if exclusion:
                row.meaningful_exclusion = exclusion
                continue
            kept.append(row)

        meta["kept_pairs"] = len(kept)
        return kept, meta

    def _invalid_brand_recommendation(self, label: str) -> str:
        if label in {"ТМК", "Без бренду"}:
            return "supplier-only/non-auto"
        if label in {"БРТ", "БелМаг", "Сімокс"}:
            return "brand alias possible"
        return "manual review"

    def _non_auto_brand_label(self, raw_brand: str) -> str:
        key = _brand_hint_key(raw_brand)
        return self.NON_AUTO_BRAND_HINTS.get(key, "")

    def _possible_non_auto_brand(self, raw_brand: str) -> bool:
        key = _brand_hint_key(raw_brand)
        return any(token in key for token in self.POSSIBLE_NON_AUTO_TOKENS)

    def _print_remote_summary(self, *, remote_stats: RemoteEvalStats):
        self.stdout.write("Remote mode summary:")
        self.stdout.write(f"- remote_checked: {remote_stats.checked}")
        self.stdout.write(f"- remote_queries: {remote_stats.queries}")
        self.stdout.write(f"- remote_hits: {remote_stats.hits}")
        self.stdout.write(f"- remote_checked_not_found: {remote_stats.checked_not_found}")
        self.stdout.write(f"- remote_errors: {remote_stats.errors}")
        self.stdout.write(f"- remote_not_checked: {remote_stats.not_checked}")

    def _classify_old_article_pattern(self, article: str) -> str:
        text = str(article or "").strip()
        if not text:
            return ""
        for name, pattern in self.OLD_ARTICLE_PATTERNS:
            if pattern.search(text):
                return name
        return ""
