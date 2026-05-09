from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services.article_lookup import AutoDbArticleLookupService
from apps.autodb.services.article_number_normalizer import ArticleNumberNormalizer
from apps.autodb.services.brand_alias_diagnostics import INVALID_AUTO_BRANDS, _brand_hint_key
from apps.autodb.services.column_helpers import find_column_name
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.autodb.services.supplier_brand_matcher import SupplierBrandMatcher
from apps.catalog.models import Product
from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand


@dataclass(frozen=True)
class CandidateRow:
    product_id: str
    raw_brand_source_field: str
    raw_brand: str
    article_source_field: str
    lookup_article: str
    gpl_code: str
    gpl_article: str
    gpl_td_article: str
    raw_name: str
    raw_category: str
    raw_group: str
    mapped_site_category: str


class Command(BaseCommand):
    help = "Read-only deep breakdown for GPL Auto_DB article_not_found rows from audit CSV."

    ARTICLE_COL_CANDIDATES = [
        "DataSupplierArticleNumber",
        "datasupplierarticlenumber",
        "PartsDataSupplierArticleNumber",
        "partsdatasupplierarticlenumber",
        "articlenumber",
        "article",
        "number",
    ]
    SUPPLIER_COL_CANDIDATES = ["supplierId", "supplierid", "SupplierId", "supplier_id", "supplier"]
    EAN_COL_CANDIDATES = ["ean", "EAN"]
    OE_COL_CANDIDATES = ["oe", "oenbr", "oenbr_clr", "oeNumber", "OENbr"]
    CROSS_COL_CANDIDATES = ["cross", "cross_number", "reference", "partsdatasupplierarticlenumber", "oenbr"]

    NON_TECDOC_KEYWORDS = (
        "автохим",
        "автохімі",
        "краск",
        "емал",
        "інструм",
        "инструм",
        "аптеч",
        "ізолент",
        "изолент",
        "аксессуар",
        "аксесуар",
        "adblue",
        "губк",
        "салфет",
        "сервет",
        "чехл",
        "накидк",
        "ароматиз",
        "бытов",
        "побутов",
        "паста",
        "очист",
        "полірол",
        "полирол",
        "шампун",
    )

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, required=True)
        parser.add_argument("--limit", type=int, default=20000)
        parser.add_argument("--candidates-csv", type=str, required=True)
        parser.add_argument("--export-csv", type=str, required=True)
        parser.add_argument("--summary-csv", type=str, required=True)

    def handle(self, *args, **options):
        supplier_code = str(options["supplier"]).strip().lower()
        if supplier_code != "gpl":
            raise CommandError("This diagnostics command currently supports only --supplier GPL.")

        limit = max(int(options.get("limit") or 0), 0)
        candidates_csv = Path(str(options["candidates_csv"]).strip()).expanduser()
        export_csv = Path(str(options["export_csv"]).strip()).expanduser()
        summary_csv = Path(str(options["summary_csv"]).strip()).expanduser()
        if not candidates_csv.exists():
            raise CommandError(f"Candidates CSV not found: {candidates_csv}")

        rows = self._load_article_not_found_rows(path=candidates_csv, limit=limit)
        if not rows:
            raise CommandError("No article_not_found rows found in candidates CSV.")

        product_map = self._product_map([row.product_id for row in rows])
        matcher = SupplierBrandMatcher()
        normalizer = ArticleNumberNormalizer()
        storage = AutoDbRawCloneStorage()
        lookup = AutoDbArticleLookupService(storage=storage)

        unique_brands = sorted({normalize_brand(row.raw_brand) for row in rows if normalize_brand(row.raw_brand)})
        brand_matches = matcher.resolve_many(unique_brands)

        remote_sync_index = self._load_remote_sync_index(Path("/private/tmp/gpl_td_article_remote_sync_real.csv"))

        row_ctx: list[dict[str, Any]] = []
        supplier_to_variants: dict[int, set[str]] = defaultdict(set)
        for row in rows:
            brand_status, supplier_id = self._resolve_brand_status(row=row, brand_matches=brand_matches)
            variants = self._build_variants(normalizer=normalizer, value=row.lookup_article)
            if brand_status == "resolved" and supplier_id is not None:
                supplier_to_variants[supplier_id].update(variants)
            row_ctx.append(
                {
                    "row": row,
                    "brand_status": brand_status,
                    "supplier_id": supplier_id,
                    "variants": variants,
                }
            )

        exact_index = self._query_variant_hits(
            storage=storage,
            table="article_numbers",
            supplier_to_variants=supplier_to_variants,
            article_col_candidates=self.ARTICLE_COL_CANDIDATES,
        )
        exact_articles_index = self._query_variant_hits(
            storage=storage,
            table="articles",
            supplier_to_variants=supplier_to_variants,
            article_col_candidates=self.ARTICLE_COL_CANDIDATES,
        )
        ean_index = self._query_variant_hits(
            storage=storage,
            table="article_ean",
            supplier_to_variants=supplier_to_variants,
            article_col_candidates=[*self.ARTICLE_COL_CANDIDATES, *self.EAN_COL_CANDIDATES],
        )
        oe_index = self._query_variant_hits(
            storage=storage,
            table="article_oe",
            supplier_to_variants=supplier_to_variants,
            article_col_candidates=[*self.ARTICLE_COL_CANDIDATES, *self.OE_COL_CANDIDATES],
        )
        cross_index = self._query_variant_hits(
            storage=storage,
            table="article_cross",
            supplier_to_variants=supplier_to_variants,
            article_col_candidates=[*self.ARTICLE_COL_CANDIDATES, *self.CROSS_COL_CANDIDATES],
        )

        counters = Counter()
        out_rows: list[dict[str, str]] = []
        for item in row_ctx:
            row = item["row"]
            brand_status = str(item["brand_status"])
            supplier_id = item["supplier_id"]
            variants = item["variants"]
            product = product_map.get(row.product_id)

            td_article_empty = "1" if not row.gpl_td_article else "0"
            local_article_found = self._has_hit(exact_index, supplier_id, variants) or self._has_hit(exact_articles_index, supplier_id, variants)
            local_article_missing = not local_article_found
            normalization_would_find = local_article_found
            article_numbers_would_find = self._has_hit(exact_index, supplier_id, variants)
            ean_would_find = self._has_hit(ean_index, supplier_id, variants)
            oe_would_find = self._has_hit(oe_index, supplier_id, variants)
            cross_would_find = self._has_hit(cross_index, supplier_id, variants)

            remote_status = self._resolve_remote_status(
                remote_sync_index=remote_sync_index,
                raw_brand=row.raw_brand,
                td_article=row.gpl_td_article,
            )
            non_tecdoc_likely = self._is_likely_non_tecdoc(row=row)
            action, reason = self._recommend_action(
                row=row,
                brand_status=brand_status,
                td_article_empty=td_article_empty == "1",
                local_article_found=local_article_found,
                normalization_would_find=normalization_would_find,
                remote_status=remote_status,
                non_tecdoc_likely=non_tecdoc_likely,
            )

            counters["total"] += 1
            if td_article_empty == "1":
                counters["td_article_empty"] += 1
            if brand_status == "unresolved":
                counters["brand_unresolved"] += 1
            if brand_status == "ambiguous":
                counters["brand_ambiguous"] += 1
            if brand_status == "resolved" and local_article_missing:
                counters["brand_resolved_local_missing"] += 1
            if brand_status == "resolved" and remote_status == "remote_checked_not_found":
                counters["brand_resolved_remote_checked_not_found"] += 1
            if brand_status == "resolved" and remote_status == "not_remote_checked":
                counters["brand_resolved_not_remote_checked"] += 1
            if non_tecdoc_likely:
                counters["likely_non_tecdoc"] += 1
            if normalization_would_find:
                counters["normalization_opportunity"] += 1
            if action == "add_brand_alias":
                counters["brand_alias_opportunity"] += 1

            out_rows.append(
                {
                    "product_id": row.product_id,
                    "display_sku": row.gpl_code or "",
                    "internal_import_key": str(getattr(product, "sku", "") or ""),
                    "raw_brand": row.raw_brand,
                    "raw_brand_source_field": row.raw_brand_source_field,
                    "raw_td_article": row.gpl_td_article,
                    "raw_article": row.gpl_article or row.lookup_article,
                    "gpl_code": row.gpl_code,
                    "raw_name": row.raw_name,
                    "raw_category": row.raw_category,
                    "raw_group": row.raw_group,
                    "mapped_site_category": row.mapped_site_category,
                    "td_article_empty": td_article_empty,
                    "brand_resolution_status": brand_status,
                    "resolved_supplier_id": str(supplier_id or ""),
                    "local_article_found": "1" if local_article_found else "0",
                    "local_article_missing": "1" if local_article_missing else "0",
                    "remote_checked_status": remote_status,
                    "normalized_article_variants": "|".join(variants),
                    "normalization_would_find": "1" if normalization_would_find else "0",
                    "article_numbers_would_find": "1" if article_numbers_would_find else "0",
                    "ean_would_find": "1" if ean_would_find else "0",
                    "oe_would_find": "1" if oe_would_find else "0",
                    "cross_would_find": "1" if cross_would_find else "0",
                    "non_tecdoc_likely": "1" if non_tecdoc_likely else "0",
                    "recommended_next_action": action,
                    "reason": reason,
                }
            )

        self._write_csv(
            export_csv,
            out_rows,
            [
                "product_id",
                "display_sku",
                "internal_import_key",
                "raw_brand",
                "raw_brand_source_field",
                "raw_td_article",
                "raw_article",
                "gpl_code",
                "raw_name",
                "raw_category",
                "raw_group",
                "mapped_site_category",
                "td_article_empty",
                "brand_resolution_status",
                "resolved_supplier_id",
                "local_article_found",
                "local_article_missing",
                "remote_checked_status",
                "normalized_article_variants",
                "normalization_would_find",
                "article_numbers_would_find",
                "ean_would_find",
                "oe_would_find",
                "cross_would_find",
                "non_tecdoc_likely",
                "recommended_next_action",
                "reason",
            ],
        )

        summary_rows = [{"metric": key, "count": str(value)} for key, value in sorted(counters.items())]
        self._write_csv(summary_csv, summary_rows, ["metric", "count"])

        self.stdout.write("diagnose_gpl_autodb_article_not_found summary:")
        for key in (
            "total",
            "td_article_empty",
            "brand_unresolved",
            "brand_ambiguous",
            "brand_resolved_local_missing",
            "brand_resolved_remote_checked_not_found",
            "brand_resolved_not_remote_checked",
            "likely_non_tecdoc",
            "normalization_opportunity",
            "brand_alias_opportunity",
        ):
            self.stdout.write(f"- {key}: {counters.get(key, 0)}")
        self.stdout.write(f"- export_csv: {export_csv}")
        self.stdout.write(f"- summary_csv: {summary_csv}")
        self.stdout.write("- UTR calls=0")
        self.stdout.write("- writes=0")

    def _load_article_not_found_rows(self, *, path: Path, limit: int) -> list[CandidateRow]:
        out: list[CandidateRow] = []
        with path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                if str(row.get("decision") or "").strip() != "article_not_found":
                    continue
                out.append(
                    CandidateRow(
                        product_id=str(row.get("product_id") or "").strip(),
                        raw_brand_source_field=str(row.get("raw_brand_source_field") or "").strip(),
                        raw_brand=str(row.get("raw_brand") or "").strip(),
                        article_source_field=str(row.get("article_source_field") or "").strip(),
                        lookup_article=str(row.get("lookup_article") or "").strip(),
                        gpl_code=str(row.get("gpl_code") or "").strip(),
                        gpl_article=str(row.get("gpl_article") or "").strip(),
                        gpl_td_article=str(row.get("gpl_td_article") or "").strip(),
                        raw_name=str(row.get("raw_name") or "").strip(),
                        raw_category=str(row.get("raw_category") or "").strip(),
                        raw_group=str(row.get("raw_group") or "").strip(),
                        mapped_site_category=str(row.get("mapped_site_category") or "").strip(),
                    )
                )
                if limit > 0 and len(out) >= limit:
                    break
        return out

    @staticmethod
    def _product_map(product_ids: list[str]) -> dict[str, Product]:
        if not product_ids:
            return {}
        rows = Product.objects.filter(id__in=product_ids).only("id", "sku")
        return {str(item.id): item for item in rows}

    def _resolve_brand_status(self, *, row: CandidateRow, brand_matches: dict[str, Any]) -> tuple[str, int | None]:
        normalized = normalize_brand(row.raw_brand)
        if not normalized:
            return "invalid", None
        if _brand_hint_key(row.raw_brand) in INVALID_AUTO_BRANDS:
            return "non_auto_or_supplier_only", None
        match = brand_matches.get(normalized)
        if match is None or match.matched_supplier_id is None:
            return "unresolved", None
        if len(match.candidates) >= 2:
            c1, c2 = match.candidates[0], match.candidates[1]
            if float(c1.confidence) == float(c2.confidence) and int(c1.supplier_id) != int(c2.supplier_id):
                return "ambiguous", None
        return "resolved", int(match.matched_supplier_id)

    @staticmethod
    def _build_variants(*, normalizer: ArticleNumberNormalizer, value: str) -> list[str]:
        variants = list(normalizer.normalize(value).search_variants)
        cleaned = str(value or "").strip().upper()
        for item in (
            cleaned,
            cleaned.replace(" ", ""),
            cleaned.replace("-", ""),
            cleaned.replace(".", ""),
            cleaned.replace("/", ""),
            cleaned.replace("/", "-"),
            cleaned.replace("-", " "),
            cleaned.upper(),
        ):
            normalized = normalize_article(item)
            if normalized and normalized not in variants:
                variants.append(normalized)
            if item and item not in variants:
                variants.append(item)
        dedupe: list[str] = []
        for item in variants:
            text = str(item or "").strip().upper()
            if text and text not in dedupe:
                dedupe.append(text)
        return dedupe[:20]

    def _query_variant_hits(
        self,
        *,
        storage: AutoDbRawCloneStorage,
        table: str,
        supplier_to_variants: dict[int, set[str]],
        article_col_candidates: list[str],
    ) -> dict[int, set[str]]:
        columns = storage.get_local_columns(table)
        if not columns:
            return {}
        article_col = find_column_name(columns, article_col_candidates)
        supplier_col = find_column_name(columns, self.SUPPLIER_COL_CANDIDATES)
        if not article_col:
            return {}

        out: dict[int, set[str]] = defaultdict(set)
        for supplier_id, variants in supplier_to_variants.items():
            values = sorted({str(item).strip() for item in variants if str(item).strip()})
            if not values:
                continue
            for start in range(0, len(values), 500):
                chunk = values[start : start + 500]
                extra = {supplier_col: supplier_id} if supplier_col else {}
                rows = storage.fetch_local_rows_in(
                    table=table,
                    column=article_col,
                    values=chunk,
                    extra_filters=extra,
                    limit=max(len(chunk) * 10, 1000),
                    columns=[article_col, *( [supplier_col] if supplier_col else [])],
                )
                for row in rows:
                    value = str(row.get(article_col) or "").strip().upper()
                    if value:
                        out[int(supplier_id)].add(value)
                        out[int(supplier_id)].add(normalize_article(value))
        return out

    @staticmethod
    def _has_hit(index: dict[int, set[str]], supplier_id: int | None, variants: list[str]) -> bool:
        if supplier_id is None:
            return False
        pool = index.get(int(supplier_id), set())
        if not pool:
            return False
        for item in variants:
            value = str(item or "").strip().upper()
            if not value:
                continue
            if value in pool or normalize_article(value) in pool:
                return True
        return False

    @staticmethod
    def _load_remote_sync_index(path: Path) -> dict[tuple[str, str], dict[str, str]]:
        if not path.exists():
            return {}
        out: dict[tuple[str, str], dict[str, str]] = {}
        with path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                key = (normalize_brand(str(row.get("raw_brand") or "")), normalize_article(str(row.get("td_article") or "")))
                if key not in out:
                    out[key] = {str(k): str(v or "") for k, v in row.items()}
        return out

    @staticmethod
    def _resolve_remote_status(*, remote_sync_index: dict[tuple[str, str], dict[str, str]], raw_brand: str, td_article: str) -> str:
        key = (normalize_brand(raw_brand), normalize_article(td_article))
        row = remote_sync_index.get(key)
        if not row:
            return "not_remote_checked"
        remote_found = str(row.get("remote_found") or "").strip()
        status = str(row.get("status") or "").strip().lower()
        if remote_found == "1" or "synced" in status or "remote_hit" in status:
            return "remote_hit_synced"
        if "not_found" in status or "remote_not_found" in status:
            return "remote_checked_not_found"
        return "remote_checked_not_found"

    def _is_likely_non_tecdoc(self, *, row: CandidateRow) -> bool:
        text = " ".join(
            [
                row.raw_name.lower(),
                row.raw_category.lower(),
                row.raw_group.lower(),
                row.mapped_site_category.lower(),
            ]
        )
        return any(token in text for token in self.NON_TECDOC_KEYWORDS)

    def _recommend_action(
        self,
        *,
        row: CandidateRow,
        brand_status: str,
        td_article_empty: bool,
        local_article_found: bool,
        normalization_would_find: bool,
        remote_status: str,
        non_tecdoc_likely: bool,
    ) -> tuple[str, str]:
        if non_tecdoc_likely:
            return "non_tecdoc_ignore", "non_tecdoc_category_or_keywords"
        if brand_status in {"invalid", "non_auto_or_supplier_only"}:
            return "non_tecdoc_ignore", "brand_non_auto_or_supplier_only"
        if brand_status == "unresolved":
            return "add_brand_alias", "brand_unresolved_local"
        if brand_status == "ambiguous":
            return "needs_manual_review", "brand_ambiguous_candidates"
        if td_article_empty:
            return "needs_manual_review", "td_article_empty"
        if local_article_found and normalization_would_find:
            return "article_normalization_rule", "variant_hits_local_tables"
        if remote_status == "not_remote_checked":
            return "sync_remote_exact", "resolved_brand_not_remote_checked"
        if remote_status == "remote_checked_not_found":
            return "investigate_remote_not_found", "remote_checked_not_found"
        return "needs_manual_review", "requires_manual_decision"

    @staticmethod
    def _write_csv(path: Path, rows: list[dict[str, str]], headers: list[str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key, "") for key in headers})
