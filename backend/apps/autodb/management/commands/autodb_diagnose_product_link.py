from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.autodb.services.article_lookup import AutoDbArticleLookupService
from apps.autodb.services.column_helpers import find_column_name
from apps.autodb.services.remote_config import AutoDbRemoteConfigError, AutoDbRemoteConfigValidator
from apps.autodb.services.supplier_brand_matcher import SupplierBrandMatcher
from apps.catalog.models import Product
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand


@dataclass(frozen=True)
class CandidateProbe:
    brand: str
    article: str
    found: bool
    supplier_id: int | None
    canonical_article_number: str
    supplier_source: str
    article_source: str
    remote_supplier_called: bool
    remote_article_called: bool
    search_variants: tuple[str, ...]
    warnings: list[str]


@dataclass(frozen=True)
class TableProbeSummary:
    table: str
    checked_values: tuple[str, ...]
    local_hits: int
    remote_hits: int
    remote_called: bool
    error: str


class Command(BaseCommand):
    help = "Diagnose why a Product has no Auto_DB_Pro link and show lookup candidates."

    ARTICLE_TABLES = (
        ("articles", ["DataSupplierArticleNumber", "datasupplierarticlenumber", "articlenumber", "article", "number"]),
        ("article_numbers", ["DataSupplierArticleNumber", "datasupplierarticlenumber", "articlenumber", "article", "number"]),
        ("article_ean", ["ean", "EAN", "barcode", "Barcode", "gtin", "upc", "article", "articlenumber"]),
        ("article_oe", ["oe", "OE", "oem", "Oem", "originalnumber", "original_number", "article", "articlenumber"]),
        ("article_cross", ["cross", "reference", "xref", "article", "articlenumber", "DataSupplierArticleNumber"]),
    )

    def add_arguments(self, parser):
        parser.add_argument("--product-id", type=str, default="", help="Product UUID")
        parser.add_argument("--search", type=str, default="", help="Search Product by name/article/sku")
        parser.add_argument("--allow-remote", action="store_true", help="Allow remote fallback in lookup")

    def handle(self, *args, **options):
        product_id = str(options.get("product_id") or "").strip()
        search = str(options.get("search") or "").strip()
        allow_remote = bool(options.get("allow_remote"))
        if not product_id and not search:
            raise CommandError("Provide --product-id or --search")

        remote_config_error = ""
        remote_check_completed = not allow_remote
        if allow_remote:
            try:
                AutoDbRemoteConfigValidator.ensure_remote_ready(allow_remote=True)
                remote_check_completed = True
            except AutoDbRemoteConfigError as exc:
                remote_config_error = str(exc)
                remote_check_completed = False

        lookup_service = AutoDbArticleLookupService()
        matcher = SupplierBrandMatcher()

        products = self._resolve_products(product_id=product_id, search=search)
        if not products:
            self.stdout.write("No Product found for diagnostics.")
            self._print_raw_offer_search(search=search)
            return

        for product in products:
            self._diagnose_product(
                product=product,
                lookup_service=lookup_service,
                matcher=matcher,
                allow_remote=allow_remote,
                remote_config_error=remote_config_error,
                remote_check_completed=remote_check_completed,
            )

    def _resolve_products(self, *, product_id: str, search: str) -> list[Product]:
        if product_id:
            try:
                return [Product.objects.select_related("brand").get(pk=product_id)]
            except Product.DoesNotExist:
                return []

        qs = Product.objects.select_related("brand").filter(
            Q(name__icontains=search)
            | Q(article__icontains=search)
            | Q(sku__icontains=search)
            | Q(autodb_article_number__icontains=search)
        )
        return list(qs.order_by("-updated_at")[:10])

    def _diagnose_product(
        self,
        *,
        product: Product,
        lookup_service: AutoDbArticleLookupService,
        matcher: SupplierBrandMatcher,
        allow_remote: bool,
        remote_config_error: str,
        remote_check_completed: bool,
    ) -> None:
        brand_name = str(getattr(product.brand, "name", "") or "")
        self.stdout.write("Auto_DB_Pro product link diagnostics:")
        self.stdout.write(f"- product_id: {product.id}")
        self.stdout.write(f"- name: {product.name}")
        self.stdout.write(f"- brand: {brand_name or '-'}")
        self.stdout.write(f"- article: {product.article or '-'}")
        self.stdout.write(f"- sku: {product.sku or '-'}")
        self.stdout.write(f"- autodb_supplier_id: {product.autodb_supplier_id or '-'}")
        self.stdout.write(f"- autodb_article_number: {product.autodb_article_number or '-'}")
        self.stdout.write(f"- autodb_article_key: {product.autodb_article_key or '-'}")
        self.stdout.write(f"- allow_remote: {allow_remote}")
        self.stdout.write(
            f"- remote_check_completed: {'true' if remote_check_completed else ('false' if allow_remote else '-')}"
        )

        if remote_config_error:
            self.stdout.write(f"- remote_config_error: {remote_config_error}")
            self.stdout.write("- lookup_status: lookup_not_completed")
            self.stdout.write("- reason: remote_config_error")
            self.stdout.write("- UTR calls: 0")
            return

        raw_offers = self._collect_raw_offers(product=product)
        self.stdout.write(f"- supplier_raw_offer_candidates: {len(raw_offers)}")
        for offer in raw_offers:
            payload_info = self._extract_payload_info(offer.raw_payload)
            self.stdout.write(
                f"  - raw_offer_id={offer.id} supplier={getattr(offer.supplier, 'code', '-') or '-'} "
                f"raw_brand={offer.brand_name or '-'} raw_article={offer.article or '-'} "
                f"normalized_article={offer.normalized_article or '-'} external_sku={offer.external_sku or '-'}"
            )
            self.stdout.write(f"    raw_product_name={offer.product_name or '-'}")
            self.stdout.write(
                f"    raw_payload_keys={', '.join(payload_info['keys']) if payload_info['keys'] else '-'}"
            )
            self.stdout.write(
                f"    candidate_article_fields={', '.join(payload_info['article_numbers']) if payload_info['article_numbers'] else '-'}"
            )
            self.stdout.write(f"    gpl_article_td={', '.join(payload_info['gpl_article_td']) if payload_info['gpl_article_td'] else '-'}")
            self.stdout.write(f"    ean_fields={', '.join(payload_info['ean']) if payload_info['ean'] else '-'}")
            self.stdout.write(f"    oe_fields={', '.join(payload_info['oe']) if payload_info['oe'] else '-'}")
            self.stdout.write(f"    cross_fields={', '.join(payload_info['cross']) if payload_info['cross'] else '-'}")
            self.stdout.write(f"    image_fields={', '.join(payload_info['images']) if payload_info['images'] else '-'}")

        brand_candidates = self._collect_brand_candidates(product=product, raw_offers=raw_offers)
        candidate_buckets = self._collect_article_candidates(product=product, raw_offers=raw_offers)
        article_candidates = candidate_buckets["article_numbers"]

        self.stdout.write(f"- brand_candidates: {', '.join(brand_candidates) if brand_candidates else '-'}")
        self.stdout.write(
            f"- article_candidates: {', '.join(article_candidates) if article_candidates else '-'}"
        )
        self.stdout.write(f"- ean_candidates: {', '.join(candidate_buckets['ean']) if candidate_buckets['ean'] else '-'}")
        self.stdout.write(f"- oe_candidates: {', '.join(candidate_buckets['oe']) if candidate_buckets['oe'] else '-'}")
        self.stdout.write(f"- cross_candidates: {', '.join(candidate_buckets['cross']) if candidate_buckets['cross'] else '-'}")

        matcher_result = matcher.resolve_many(brand_candidates)
        supplier_candidates = self._collect_supplier_candidates(product=product, brand_candidates=brand_candidates, matcher_result=matcher_result)
        self.stdout.write("- supplier_candidates:")
        if not supplier_candidates:
            self.stdout.write("  - -")
        for brand in brand_candidates:
            matched = matcher_result.get(normalize_brand(brand))
            if not matched:
                continue
            self.stdout.write(
                f"  - brand={brand} normalized={matched.normalized_brand} "
                f"matched_supplier_id={matched.matched_supplier_id or '-'} confidence={matched.confidence:.2f} reason={matched.reason}"
            )

        probes: list[CandidateProbe] = []
        probe_errors: list[str] = []
        for brand in brand_candidates[:3]:
            for article in article_candidates[:8]:
                try:
                    lookup = lookup_service.lookup(brand_name=brand, article=article, allow_remote=allow_remote)
                except Exception as exc:  # noqa: BLE001
                    probe_errors.append(str(exc))
                    continue
                probes.append(
                    CandidateProbe(
                        brand=brand,
                        article=article,
                        found=lookup.found,
                        supplier_id=lookup.supplier_id,
                        canonical_article_number=lookup.canonical_article_number,
                        supplier_source=lookup.supplier_source,
                        article_source=lookup.article_source,
                        remote_supplier_called=lookup.remote_supplier_called,
                        remote_article_called=lookup.remote_article_called,
                        search_variants=lookup.article_search_variants,
                        warnings=list(lookup.warnings),
                    )
                )
                if lookup.found:
                    break
            if any(item.found for item in probes):
                break

        if probes:
            self.stdout.write("- lookup_probes:")
            for item in probes:
                self.stdout.write(
                    f"  - brand={item.brand} article={item.article} found={item.found} "
                    f"supplier_id={item.supplier_id or '-'} canonical_article={item.canonical_article_number or '-'} "
                    f"supplier_source={item.supplier_source} article_source={item.article_source} "
                    f"remote_supplier_called={item.remote_supplier_called} remote_article_called={item.remote_article_called} "
                    f"warnings={','.join(item.warnings) if item.warnings else '-'}"
                )
                self.stdout.write(
                    f"    article_variants_checked={', '.join(item.search_variants) if item.search_variants else '-'}"
                )
        if probe_errors:
            self.stdout.write("- lookup_probe_errors:")
            for item in probe_errors[:10]:
                self.stdout.write(f"  - {item}")

        remote_lookup_failed = bool(allow_remote and probe_errors)

        table_probes = self._probe_reference_tables(
            lookup_service=lookup_service,
            supplier_ids=supplier_candidates,
            candidate_buckets=candidate_buckets,
            allow_remote=allow_remote,
        )
        self.stdout.write("- table_probes:")
        for item in table_probes:
            self.stdout.write(
                f"  - table={item.table} local_hits={item.local_hits} remote_hits={item.remote_hits} "
                f"remote_called={item.remote_called} values_checked={', '.join(item.checked_values) if item.checked_values else '-'}"
            )
            if item.error:
                self.stdout.write(f"    error={item.error}")

        found_probe = next((item for item in probes if item.found), None)
        if found_probe:
            self.stdout.write("- link_possible: yes")
            self.stdout.write(
                f"- link_candidate: supplier_id={found_probe.supplier_id} article_number={found_probe.canonical_article_number}"
            )
        else:
            self.stdout.write("- link_possible: no")
            self.stdout.write("- recommendation: create manual mapping with manual_confirmed=true and confidence>=0.500")

        reason = self._resolve_reason(
            product=product,
            brand_candidates=brand_candidates,
            article_candidates=article_candidates,
            matcher_result=matcher_result,
            probes=probes,
            remote_lookup_failed=remote_lookup_failed,
        )
        lookup_status = "lookup_not_completed" if reason in {"remote_config_error", "lookup_not_completed"} else "completed"
        self.stdout.write(f"- lookup_status: {lookup_status}")
        self.stdout.write(f"- reason: {reason}")
        self.stdout.write("- UTR calls: 0")

    def _collect_raw_offers(self, *, product: Product) -> list[SupplierRawOffer]:
        filters = Q(matched_product=product)
        if product.article:
            filters |= Q(article__iexact=product.article)
        if product.sku:
            filters |= Q(external_sku__iexact=product.sku)
        return list(
            SupplierRawOffer.objects.filter(filters)
            .order_by("-updated_at")
            .select_related("supplier", "source")[:30]
        )

    def _collect_brand_candidates(self, *, product: Product, raw_offers: list[SupplierRawOffer]) -> list[str]:
        values = [str(getattr(product.brand, "name", "") or "")]
        values.extend(str(item.brand_name or "") for item in raw_offers)
        result: list[str] = []
        seen = set()
        for value in values:
            clean = value.strip()
            norm = normalize_brand(clean)
            if norm and norm not in seen:
                seen.add(norm)
                result.append(clean)
        return result

    def _collect_article_candidates(self, *, product: Product, raw_offers: list[SupplierRawOffer]) -> dict[str, list[str]]:
        article_numbers: list[str] = []
        ean_values: list[str] = []
        oe_values: list[str] = []
        cross_values: list[str] = []

        self._append_unique(article_numbers, str(product.article or ""))
        self._append_unique(article_numbers, str(product.autodb_article_number or ""))
        self._append_unique(article_numbers, str(product.sku or ""))

        for offer in raw_offers:
            self._append_unique(article_numbers, str(offer.article or ""))
            self._append_unique(article_numbers, str(offer.normalized_article or ""))
            self._append_unique(article_numbers, str(offer.external_sku or ""))

            payload_info = self._extract_payload_info(offer.raw_payload)
            for value in payload_info["article_numbers"]:
                self._append_unique(article_numbers, value)
            for value in payload_info["gpl_article_td"]:
                self._append_unique(article_numbers, value)
            for value in payload_info["ean"]:
                self._append_unique(ean_values, value)
            for value in payload_info["oe"]:
                self._append_unique(oe_values, value)
            for value in payload_info["cross"]:
                self._append_unique(cross_values, value)

        return {
            "article_numbers": article_numbers,
            "ean": ean_values,
            "oe": oe_values,
            "cross": cross_values,
        }

    def _collect_supplier_candidates(self, *, product: Product, brand_candidates: list[str], matcher_result: dict) -> list[int]:
        values: list[int] = []
        if product.autodb_supplier_id:
            values.append(int(product.autodb_supplier_id))
        for brand in brand_candidates:
            match = matcher_result.get(normalize_brand(brand))
            supplier_id = getattr(match, "matched_supplier_id", None)
            if supplier_id and supplier_id not in values:
                values.append(int(supplier_id))
        return values

    def _probe_reference_tables(
        self,
        *,
        lookup_service: AutoDbArticleLookupService,
        supplier_ids: list[int],
        candidate_buckets: dict[str, list[str]],
        allow_remote: bool,
    ) -> list[TableProbeSummary]:
        results: list[TableProbeSummary] = []
        for table, column_candidates in self.ARTICLE_TABLES:
            if table in {"article_ean"}:
                values = candidate_buckets.get("ean") or candidate_buckets.get("article_numbers")
            elif table in {"article_oe"}:
                values = candidate_buckets.get("oe") or candidate_buckets.get("article_numbers")
            elif table in {"article_cross"}:
                values = candidate_buckets.get("cross") or candidate_buckets.get("article_numbers")
            else:
                values = candidate_buckets.get("article_numbers")
            probe = self._probe_one_table(
                lookup_service=lookup_service,
                table=table,
                article_column_candidates=column_candidates,
                supplier_ids=supplier_ids,
                values=values or [],
                allow_remote=allow_remote,
            )
            results.append(probe)
        return results

    def _probe_one_table(
        self,
        *,
        lookup_service: AutoDbArticleLookupService,
        table: str,
        article_column_candidates: list[str],
        supplier_ids: list[int],
        values: list[str],
        allow_remote: bool,
    ) -> TableProbeSummary:
        storage = lookup_service.storage
        checked_values = tuple(values[:12])
        if not checked_values:
            return TableProbeSummary(
                table=table,
                checked_values=(),
                local_hits=0,
                remote_hits=0,
                remote_called=False,
                error="",
            )

        local_hits = 0
        remote_hits = 0
        remote_called = False
        error = ""

        try:
            local_columns = list(storage.get_local_columns(table))
            article_column = find_column_name(local_columns, article_column_candidates)
            supplier_column = find_column_name(local_columns, ["supplierId", "supplierid", "supplier_id", "supplier"])
            if article_column:
                scope = supplier_ids or [None]
                for supplier_id in scope:
                    for value in checked_values:
                        filters: dict[str, Any] = {article_column: value}
                        if supplier_id is not None and supplier_column:
                            filters[supplier_column] = supplier_id
                        rows = storage.fetch_local_rows(table=table, filters=filters, limit=1)
                        if rows:
                            local_hits += 1
        except Exception as exc:  # noqa: BLE001
            error = f"local_probe_error:{exc}"

        if allow_remote:
            try:
                remote_columns = storage.get_remote_columns(table)
                remote_article_column = find_column_name(remote_columns, article_column_candidates)
                remote_supplier_column = find_column_name(remote_columns, ["supplierId", "supplierid", "supplier_id", "supplier"])
                if remote_article_column:
                    remote_called = True
                    scope = supplier_ids or [None]
                    for supplier_id in scope:
                        for value in checked_values:
                            filters = {remote_article_column: value}
                            if supplier_id is not None and remote_supplier_column:
                                filters[remote_supplier_column] = supplier_id
                            rows = storage.fetch_remote_rows_exact(table=table, filters=filters, limit=1)
                            if rows:
                                remote_hits += 1
            except Exception as exc:  # noqa: BLE001
                message = f"remote_probe_error:{exc}"
                error = f"{error};{message}" if error else message

        return TableProbeSummary(
            table=table,
            checked_values=checked_values,
            local_hits=local_hits,
            remote_hits=remote_hits,
            remote_called=remote_called,
            error=error,
        )

    def _resolve_reason(
        self,
        *,
        product: Product,
        brand_candidates: list[str],
        article_candidates: list[str],
        matcher_result: dict,
        probes: list[CandidateProbe],
        remote_lookup_failed: bool,
    ) -> str:
        if remote_lookup_failed:
            return "lookup_not_completed"
        if product.autodb_supplier_id and product.autodb_article_number:
            return "already_linked"
        if not brand_candidates:
            return "missing_product_brand"
        if not article_candidates:
            return "missing_article_candidates"
        has_supplier_match = any((matcher_result.get(normalize_brand(item)) and matcher_result[normalize_brand(item)].matched_supplier_id) for item in brand_candidates)
        if not has_supplier_match:
            return "brand_not_found_in_suppliers"
        if any(item.found for item in probes):
            return "link_found_in_probe"
        return "article_not_found_for_supplier"

    def _extract_payload_info(self, payload: Any) -> dict[str, list[str]]:
        result = {
            "keys": [],
            "article_numbers": [],
            "gpl_article_td": [],
            "ean": [],
            "oe": [],
            "cross": [],
            "images": [],
        }
        if not isinstance(payload, dict):
            return result

        for key in payload.keys():
            text_key = str(key).strip()
            if text_key:
                result["keys"].append(text_key)

        pairs = self._flatten_payload_pairs(payload)
        for raw_key, raw_value in pairs:
            key = str(raw_key or "").strip().lower()
            value = str(raw_value or "").strip()
            if not value:
                continue

            if raw_key in {"Артикул ТД", "article_td", "manufacturer_article"}:
                self._append_unique(result["gpl_article_td"], value)

            if self._looks_like_article_key(key):
                self._append_unique(result["article_numbers"], value)
            if self._looks_like_ean_key(key):
                self._append_unique(result["ean"], value)
            if self._looks_like_oe_key(key):
                self._append_unique(result["oe"], value)
            if self._looks_like_cross_key(key):
                self._append_unique(result["cross"], value)
            if self._looks_like_image_key(key):
                self._append_unique(result["images"], value)

        result["keys"] = sorted({item for item in result["keys"]})[:40]
        return result

    def _flatten_payload_pairs(self, payload: Any, *, prefix: str = "", depth: int = 0) -> list[tuple[str, str]]:
        if depth > 2:
            return []
        result: list[tuple[str, str]] = []
        if isinstance(payload, dict):
            for key, value in payload.items():
                full_key = f"{prefix}.{key}" if prefix else str(key)
                if isinstance(value, (dict, list, tuple)):
                    result.extend(self._flatten_payload_pairs(value, prefix=full_key, depth=depth + 1))
                else:
                    result.append((str(key), str(value)))
        elif isinstance(payload, (list, tuple)):
            for index, value in enumerate(payload):
                full_key = f"{prefix}[{index}]"
                if isinstance(value, (dict, list, tuple)):
                    result.extend(self._flatten_payload_pairs(value, prefix=full_key, depth=depth + 1))
                else:
                    result.append((prefix, str(value)))
        return result

    def _looks_like_article_key(self, key: str) -> bool:
        return any(token in key for token in ("article", "артикул", "partnumber", "part_number", "sku", "код", "number"))

    def _looks_like_ean_key(self, key: str) -> bool:
        return any(token in key for token in ("ean", "barcode", "bar_code", "gtin", "upc", "штрих"))

    def _looks_like_oe_key(self, key: str) -> bool:
        if any(token in key for token in ("oem", "original", "oe_", "_oe")):
            return True
        return bool(re.search(r"(^|[^a-z])oe([^a-z]|$)", key))

    def _looks_like_cross_key(self, key: str) -> bool:
        return any(token in key for token in ("cross", "xref", "reference", "замен", "анал") )

    def _looks_like_image_key(self, key: str) -> bool:
        return any(token in key for token in ("image", "img", "photo", "picture", "url"))

    def _append_unique(self, target: list[str], value: str) -> None:
        text = str(value or "").strip()
        if not text:
            return
        dedupe_key = text.upper()
        seen = {item.upper() for item in target}
        if dedupe_key in seen:
            return
        target.append(text)

    def _print_raw_offer_search(self, *, search: str) -> None:
        if not search:
            return
        rows = (
            SupplierRawOffer.objects.filter(
                Q(article__icontains=search)
                | Q(external_sku__icontains=search)
                | Q(product_name__icontains=search)
            )
            .order_by("-updated_at")
            .values("id", "brand_name", "article", "external_sku", "product_name", "matched_product_id")[:20]
        )
        if not rows:
            self.stdout.write("- raw offers by search: no matches")
            return
        self.stdout.write("- raw offers by search:")
        for row in rows:
            self.stdout.write(
                f"  - raw_offer_id={row['id']} brand={row['brand_name'] or '-'} "
                f"article={row['article'] or '-'} external_sku={row['external_sku'] or '-'} "
                f"matched_product_id={row['matched_product_id'] or '-'}"
            )
