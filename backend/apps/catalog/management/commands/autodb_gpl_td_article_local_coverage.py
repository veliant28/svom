from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.models import AutoDbSupplierBrandAlias
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.catalog.models import Product
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand


class Command(BaseCommand):
    help = "Read-only local Auto_DB coverage for GPL brand+TD article pairs."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, required=True, help="Supplier code, e.g. GPL")
        parser.add_argument("--limit", type=int, default=20000, help="Max products to inspect")
        parser.add_argument("--export-csv", type=str, required=True, help="Coverage CSV path")

    def handle(self, *args, **options):
        supplier_code = str(options.get("supplier") or "").strip().lower()
        if not supplier_code:
            raise CommandError("Provide --supplier")
        limit = max(int(options.get("limit") or 0), 0)
        export_csv = str(options.get("export_csv") or "").strip()
        if not export_csv:
            raise CommandError("Provide --export-csv")

        products_qs = (
            Product.objects.select_related("category", "brand")
            .filter(supplier_offers__supplier__code=supplier_code)
            .distinct()
            .order_by("id")
        )
        if limit > 0:
            products_qs = products_qs[:limit]
        products = list(products_qs)
        product_ids = [str(item.id) for item in products]

        latest_raw_map = self._latest_raw_offers_map(supplier_code=supplier_code, product_ids=product_ids)
        storage = AutoDbRawCloneStorage()
        supplier_index = self._build_local_supplier_index(storage=storage)
        alias_index = self._build_alias_index()

        prepared_rows: list[dict[str, Any]] = []
        local_pair_candidates: list[tuple[int, str]] = []
        unresolved_brand_counter: Counter[str] = Counter()
        missing_pair_counter: Counter[str] = Counter()
        invalid_td_count = 0

        for product in products:
            pid = str(product.id)
            raw = latest_raw_map.get(pid)
            if raw is None:
                continue

            payload = raw.raw_payload if isinstance(raw.raw_payload, dict) else {}
            gpl_code = self._payload_pick(payload, ("Код", "код", "code")) or str(raw.external_sku or "").strip()
            gpl_article = self._payload_pick(payload, ("Артикул", "article")) or str(raw.article or "").strip()
            gpl_td_article = self._payload_pick(payload, ("Артикул ТД", "Артикул ТД.", "article_td"))
            raw_brand = self._payload_pick(payload, ("Група ТД", "Группа ТД", "group")) or str(raw.brand_name or "").strip()
            lookup_article = gpl_td_article or gpl_article
            mapped_site_category = str(getattr(product.category, "name", "") or "")
            raw_name = str(raw.product_name or "").strip()
            raw_category = self._payload_pick(payload, ("Категорія", "Категория", "category"))

            supplier_id = self._resolve_supplier_id_local(
                brand_name=raw_brand,
                supplier_index=supplier_index,
                alias_index=alias_index,
            )

            if gpl_td_article:
                td_status = "has_td_article"
            else:
                td_status = "missing_td_article"
                invalid_td_count += 1

            if supplier_id is None:
                supplier_resolution_status = "brand_unresolved_local"
                unresolved_brand_counter[raw_brand or "(empty)"] += 1
            else:
                supplier_resolution_status = "brand_resolved_local"

            prepared = {
                "product_id": pid,
                "raw_brand": raw_brand,
                "td_article": gpl_td_article,
                "lookup_article": lookup_article,
                "gpl_code": gpl_code,
                "gpl_article": gpl_article,
                "raw_name": raw_name,
                "raw_category": raw_category,
                "mapped_site_category": mapped_site_category,
                "resolved_supplier_id": str(supplier_id or ""),
                "supplier_resolution_status": supplier_resolution_status,
                "td_status": td_status,
            }
            prepared_rows.append(prepared)

            if supplier_id is not None and lookup_article:
                local_pair_candidates.append((supplier_id, lookup_article))
            elif supplier_id is not None and not lookup_article:
                missing_pair_counter[f"{raw_brand}::{gpl_td_article or gpl_article or ''}"] += 1

        existing_pairs = self._load_local_article_pairs(storage=storage, pairs=local_pair_candidates)

        output_rows: list[dict[str, str]] = []
        counters = Counter()
        missing_brand_td_counter: Counter[str] = Counter()
        brand_total_counter: Counter[str] = Counter()
        for row in prepared_rows:
            raw_brand = str(row.get("raw_brand") or "")
            lookup_article = str(row.get("lookup_article") or "")
            supplier_id = int(row["resolved_supplier_id"]) if row.get("resolved_supplier_id") else None
            brand_total_counter[raw_brand or "(empty)"] += 1
            counters["total_products"] += 1

            local_found = False
            reason = ""
            local_article_key = ""
            if row["td_status"] == "missing_td_article":
                counters["rows_without_td_article"] += 1
                reason = "missing_td_article"
            else:
                counters["rows_with_td_article"] += 1

            if supplier_id is None:
                counters["brand_unresolved_count"] += 1
                reason = reason or "brand_unresolved_local"
            else:
                counters["brand_resolved_count"] += 1
                if lookup_article:
                    normalized = normalize_article(lookup_article)
                    marker = (supplier_id, normalized or lookup_article)
                    local_found = marker in existing_pairs
                    if local_found:
                        counters["local_article_found_count"] += 1
                        local_article_key = f"{supplier_id}:{lookup_article}"
                        reason = reason or "local_article_found"
                    else:
                        counters["local_article_missing_count"] += 1
                        missing_brand_td_counter[f"{raw_brand}::{lookup_article}"] += 1
                        reason = reason or "local_article_missing"
                else:
                    counters["invalid_empty_td_article_count"] += 1
                    reason = reason or "empty_lookup_article"

            output_rows.append(
                {
                    "product_id": str(row["product_id"]),
                    "raw_brand": raw_brand,
                    "td_article": str(row.get("td_article") or ""),
                    "gpl_code": str(row.get("gpl_code") or ""),
                    "gpl_article": str(row.get("gpl_article") or ""),
                    "raw_name": str(row.get("raw_name") or ""),
                    "raw_category": str(row.get("raw_category") or ""),
                    "mapped_site_category": str(row.get("mapped_site_category") or ""),
                    "resolved_supplier_id": str(row.get("resolved_supplier_id") or ""),
                    "supplier_resolution_status": str(row.get("supplier_resolution_status") or ""),
                    "local_article_found": "1" if local_found else "0",
                    "local_article_key": local_article_key,
                    "reason": reason,
                }
            )

        unique_brand_td_pairs = {
            (str(row.get("raw_brand") or "").strip(), str(row.get("lookup_article") or "").strip())
            for row in prepared_rows
            if str(row.get("lookup_article") or "").strip()
        }
        counters["unique_brand_td_pairs"] = len(unique_brand_td_pairs)

        local_found = counters.get("local_article_found_count", 0)
        local_missing = counters.get("local_article_missing_count", 0)
        coverage_pct = (float(local_found) / float(local_found + local_missing) * 100.0) if (local_found + local_missing) > 0 else 0.0

        self._export_csv(path=export_csv, rows=output_rows)

        self.stdout.write("autodb_gpl_td_article_local_coverage summary:")
        self.stdout.write(f"- total_products: {counters.get('total_products', 0)}")
        self.stdout.write(f"- rows_with_td_article: {counters.get('rows_with_td_article', 0)}")
        self.stdout.write(f"- rows_without_td_article: {counters.get('rows_without_td_article', 0)}")
        self.stdout.write(f"- unique_brand_td_pairs: {counters.get('unique_brand_td_pairs', 0)}")
        self.stdout.write(f"- brand_resolved_count: {counters.get('brand_resolved_count', 0)}")
        self.stdout.write(f"- brand_unresolved_count: {counters.get('brand_unresolved_count', 0)}")
        self.stdout.write(f"- local_article_found_count: {local_found}")
        self.stdout.write(f"- local_article_missing_count: {local_missing}")
        self.stdout.write(f"- local_coverage_pct: {coverage_pct:.2f}")
        self.stdout.write(f"- invalid_empty_td_article_count: {invalid_td_count}")
        self.stdout.write("- top missing brands by product_count:")
        for key, value in unresolved_brand_counter.most_common(20):
            self.stdout.write(f"  - {key}: {value}")
        self.stdout.write("- top missing brand+td_article examples:")
        for key, value in missing_brand_td_counter.most_common(30):
            self.stdout.write(f"  - {key}: {value}")
        self.stdout.write("- top brands total:")
        for key, value in brand_total_counter.most_common(20):
            self.stdout.write(f"  - {key}: {value}")
        self.stdout.write(f"- csv: {export_csv}")
        self.stdout.write("- remote_queries=0")
        self.stdout.write("- writes=0")
        self.stdout.write("- UTR calls=0")

    @staticmethod
    def _payload_pick(payload: dict[str, Any], keys: tuple[str, ...]) -> str:
        for key in keys:
            value = str(payload.get(key) or "").strip()
            if value:
                return value
        return ""

    @staticmethod
    def _latest_raw_offers_map(*, supplier_code: str, product_ids: list[str]) -> dict[str, SupplierRawOffer]:
        if not product_ids:
            return {}
        rows = (
            SupplierRawOffer.objects.filter(source__code=supplier_code, matched_product_id__in=product_ids)
            .order_by("matched_product_id", "-updated_at", "-id")
            .only("id", "matched_product_id", "brand_name", "article", "product_name", "raw_payload", "external_sku")
        )
        out: dict[str, SupplierRawOffer] = {}
        for item in rows.iterator(chunk_size=500):
            key = str(item.matched_product_id or "")
            if key and key not in out:
                out[key] = item
        return out

    @staticmethod
    def _build_alias_index() -> dict[str, int]:
        out: dict[str, int] = {}
        aliases = (
            AutoDbSupplierBrandAlias.objects.filter(is_active=True)
            .order_by("-manual_confirmed", "-confidence", "updated_at", "id")
            .values("normalized_raw_brand", "autodb_supplier_id")
        )
        for row in aliases.iterator(chunk_size=500):
            key = normalize_brand(str(row.get("normalized_raw_brand") or ""))
            supplier_id = int(row.get("autodb_supplier_id") or 0)
            if key and supplier_id > 0 and key not in out:
                out[key] = supplier_id
        return out

    @staticmethod
    def _build_local_supplier_index(storage: AutoDbRawCloneStorage) -> dict[str, int]:
        columns = storage.get_local_columns("suppliers")
        if not columns:
            return {}
        names = [name for name in ("id", "matchcode", "description", "fulldescription") if storage.column_exists(table="suppliers", column=name)]
        if not names:
            return {}
        rows = storage.fetch_local_rows(table="suppliers", limit=100000, columns=names)
        out: dict[str, int] = {}
        for row in rows:
            supplier_id = int(row.get("id") or 0)
            if supplier_id <= 0:
                continue
            for field in ("matchcode", "description", "fulldescription"):
                key = normalize_brand(str(row.get(field) or ""))
                if key and key not in out:
                    out[key] = supplier_id
        return out

    @staticmethod
    def _resolve_supplier_id_local(*, brand_name: str, supplier_index: dict[str, int], alias_index: dict[str, int]) -> int | None:
        key = normalize_brand(brand_name)
        if not key:
            return None
        if key in alias_index:
            return int(alias_index[key])
        if key in supplier_index:
            return int(supplier_index[key])
        return None

    def _load_local_article_pairs(self, *, storage: AutoDbRawCloneStorage, pairs: list[tuple[int, str]]) -> set[tuple[int, str]]:
        if not pairs:
            return set()
        by_supplier: dict[int, set[str]] = defaultdict(set)
        for supplier_id, article in pairs:
            value = str(article or "").strip()
            if not value:
                continue
            by_supplier[int(supplier_id)].add(value)
            normalized = normalize_article(value)
            if normalized:
                by_supplier[int(supplier_id)].add(normalized)

        found: set[tuple[int, str]] = set()
        for table in ("article_numbers", "articles"):
            supplier_col = storage.first_existing_column(table=table, candidates=["supplierid", "supplier_id"])
            article_col = storage.first_existing_column(
                table=table,
                candidates=["datasupplierarticlenumber", "DataSupplierArticleNumber", "article", "articlenumber", "number"],
            )
            if not supplier_col or not article_col:
                continue

            for supplier_id, values in by_supplier.items():
                if not values:
                    continue
                ordered_values = sorted(values)
                for offset in range(0, len(ordered_values), 800):
                    chunk = ordered_values[offset : offset + 800]
                    rows = storage.fetch_local_rows_in(
                        table=table,
                        column=article_col,
                        values=chunk,
                        extra_filters={supplier_col: supplier_id},
                        limit=max(len(chunk) * 4, 200),
                        columns=[supplier_col, article_col],
                    )
                    for row in rows:
                        raw_value = str(row.get(article_col) or "").strip()
                        if not raw_value:
                            continue
                        key = normalize_article(raw_value) or raw_value
                        found.add((int(supplier_id), key))
        return found

    @staticmethod
    def _export_csv(*, path: str, rows: list[dict[str, str]]) -> None:
        output = Path(path).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        headers = [
            "product_id",
            "raw_brand",
            "td_article",
            "gpl_code",
            "gpl_article",
            "raw_name",
            "raw_category",
            "mapped_site_category",
            "resolved_supplier_id",
            "supplier_resolution_status",
            "local_article_found",
            "local_article_key",
            "reason",
        ]
        with output.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
