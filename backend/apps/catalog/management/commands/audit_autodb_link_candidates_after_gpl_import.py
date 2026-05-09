from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services.article_lookup import AutoDbArticleLookupService
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.catalog.models import Product
from apps.catalog.services.autodb_link_compatibility import evaluate_category_compatibility
from apps.catalog.services.linked_semantic_audit import detect_semantic_conflicts
from apps.pricing.models import SupplierOffer
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand


class Command(BaseCommand):
    help = "Read-only audit of Auto-DB link candidates after GPL import (no writes)."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, required=True, help="Supplier code, e.g. GPL")
        parser.add_argument("--limit", type=int, default=1000, help="Max products to audit")
        parser.add_argument(
            "--article-source",
            type=str,
            default="auto",
            choices=("auto", "td_article", "raw_article"),
            help="Lookup article source policy",
        )
        parser.add_argument("--export-csv", type=str, required=True, help="CSV export path")

    def handle(self, *args, **options):
        supplier_code = str(options.get("supplier") or "").strip().lower()
        if not supplier_code:
            raise CommandError("Provide --supplier")
        limit = max(int(options.get("limit") or 0), 0)
        article_source_mode = str(options.get("article_source") or "auto").strip().lower()
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
        supplier_offer_map = self._supplier_offer_map(supplier_code=supplier_code, product_ids=product_ids)
        lookup_service = AutoDbArticleLookupService()
        storage = AutoDbRawCloneStorage()

        rows: list[dict[str, str]] = []
        counters = Counter()
        brand_counters: Counter[str] = Counter()
        category_counters: Counter[str] = Counter()
        semantic_conflict_examples: list[str] = []
        lookup_cache: dict[tuple[str, str], object] = {}

        for product in products:
            pid = str(product.id)
            raw = latest_raw_map.get(pid)
            if raw is None:
                continue

            supplier_offer_id = supplier_offer_map.get(pid, "")
            payload = raw.raw_payload if isinstance(raw.raw_payload, dict) else {}
            payload_brand = self._payload_pick(payload, ("Група ТД", "Группа ТД", "group"))
            payload_article = self._payload_pick(payload, ("Артикул", "article"))
            payload_td_article = self._payload_pick(payload, ("Артикул ТД", "Артикул ТД.", "article_td"))
            gpl_code = self._payload_pick(payload, ("Код", "код", "code")) or str(raw.external_sku or "").strip()
            gpl_article = payload_article or str(raw.article or "").strip()
            gpl_td_article = payload_td_article
            raw_brand, raw_brand_source_field = self._resolve_lookup_brand(
                payload_brand=payload_brand,
                raw_brand_name=str(raw.brand_name or "").strip(),
                product_brand_name=str(getattr(getattr(product, "brand", None), "name", "") or "").strip(),
            )
            lookup_article, article_source_field = self._resolve_lookup_article(
                supplier_code=supplier_code,
                article_source_mode=article_source_mode,
                gpl_td_article=gpl_td_article,
                payload_article=payload_article,
                raw_article=str(raw.article or "").strip(),
            )
            raw_name = str(raw.product_name or "").strip()
            raw_category = str(payload.get("Категорія") or payload.get("category") or "").strip()
            raw_group = str(payload.get("Група ТД") or payload.get("group") or "").strip()
            raw_description = str(payload.get("Опис") or payload.get("description") or "").strip()
            gpl_image_url = self._extract_image_url(payload=payload)
            mapped_site_category = str(getattr(product.category, "name", "") or "")

            lookup_key = (raw_brand, lookup_article)
            lookup = lookup_cache.get(lookup_key)
            if lookup is None:
                lookup = lookup_service.lookup(
                    brand_name=raw_brand,
                    article=lookup_article,
                    allow_remote=False,
                )
                lookup_cache[lookup_key] = lookup
            counters["checked_products"] += 1

            candidate_title = ""
            candidate_group = ""
            if lookup.supplier_id and lookup.canonical_article_number:
                article_row = self._find_local_article_row(
                    storage=storage,
                    supplier_id=int(lookup.supplier_id),
                    article_number=str(lookup.canonical_article_number),
                )
                candidate_title = str(
                    article_row.get("NormalizedDescription")
                    or article_row.get("ArticleDescription")
                    or article_row.get("Description")
                    or article_row.get("name")
                    or ""
                ).strip()
                candidate_group = str(
                    article_row.get("GenericArticleDescription")
                    or article_row.get("AssemblyGroup")
                    or article_row.get("product_group")
                    or ""
                ).strip()

            brand_match_score = self._brand_match_score(raw_brand=raw_brand, candidate_brand=lookup.canonical_brand)
            article_match_score = self._article_match_score(raw_article=lookup_article, candidate_article=lookup.canonical_article_number)

            semantic_conflicts = detect_semantic_conflicts(
                raw_brand=raw_brand,
                raw_text=" | ".join([raw_name, raw_category, raw_group, raw_description]),
                product_text=candidate_title,
                category_text=mapped_site_category,
                autodb_title_text=candidate_group,
            )
            semantic_score = 0.0 if semantic_conflicts else 1.0
            category_compatibility_score, _ = evaluate_category_compatibility(
                raw_category=raw_category,
                raw_group=raw_group,
                mapped_site_category=mapped_site_category,
                candidate_group=candidate_group,
                candidate_title=candidate_title,
            )

            decision, reason, blocker_type = self._decide(
                found=lookup.found,
                brand_match_score=brand_match_score,
                article_match_score=article_match_score,
                semantic_conflicts=semantic_conflicts,
                category_compatibility_score=category_compatibility_score,
            )
            counters[decision] += 1
            brand_counters[raw_brand or "(empty)"] += 1
            category_counters[mapped_site_category or "(uncategorized)"] += 1

            if decision == "semantic_conflict" and len(semantic_conflict_examples) < 20:
                semantic_conflict_examples.append(
                    f"{pid} | {raw_brand} {lookup_article} | raw={raw_name[:70]} | candidate={candidate_title[:70]} | {reason}"
                )

            rows.append(
                {
                    "product_id": pid,
                    "supplier_raw_offer_id": str(raw.id),
                    "supplier_offer_id": supplier_offer_id,
                    "raw_brand_source_field": raw_brand_source_field,
                    "raw_brand": raw_brand,
                    "article_source_field": article_source_field,
                    "lookup_article": lookup_article,
                    "raw_article": gpl_article,
                    "gpl_code": gpl_code,
                    "gpl_article": gpl_article,
                    "gpl_td_article": gpl_td_article,
                    "raw_name": raw_name,
                    "raw_category": raw_category,
                    "raw_group": raw_group,
                    "mapped_site_category": mapped_site_category,
                    "gpl_image_url": gpl_image_url,
                    "candidate_autodb_supplier_id": str(lookup.supplier_id or ""),
                    "candidate_autodb_article_number": str(lookup.canonical_article_number or ""),
                    "candidate_autodb_title": candidate_title,
                    "candidate_autodb_group": candidate_group,
                    "brand_match_score": f"{brand_match_score:.3f}",
                    "article_match_score": f"{article_match_score:.3f}",
                    "semantic_score": f"{semantic_score:.3f}",
                    "category_compatibility_score": f"{category_compatibility_score:.3f}",
                    "decision": decision,
                    "reason": reason,
                    "blocker_type": blocker_type,
                }
            )

        self._export_csv(path=export_csv, rows=rows)

        self.stdout.write("audit_autodb_link_candidates_after_gpl_import summary:")
        self.stdout.write(f"- article_source_mode: {article_source_mode}")
        self.stdout.write(f"- checked products: {counters.get('checked_products', 0)}")
        self.stdout.write(f"- safe_link_candidates: {counters.get('safe_link_candidate', 0)}")
        self.stdout.write(f"- semantic_conflict: {counters.get('semantic_conflict', 0)}")
        self.stdout.write(f"- needs_review: {counters.get('needs_review', 0)}")
        self.stdout.write(f"- article_not_found: {counters.get('article_not_found', 0)}")
        self.stdout.write(f"- brand_ambiguous: {counters.get('brand_ambiguous', 0)}")
        self.stdout.write(f"- csv: {export_csv}")
        self.stdout.write("- by decision:")
        for key, value in sorted(counters.items(), key=lambda item: (-item[1], item[0])):
            self.stdout.write(f"  - {key}: {value}")
        self.stdout.write("- by brand (top 20):")
        for key, value in brand_counters.most_common(20):
            self.stdout.write(f"  - {key}: {value}")
        self.stdout.write("- by mapped_site_category (top 20):")
        for key, value in category_counters.most_common(20):
            self.stdout.write(f"  - {key}: {value}")
        self._print_top_rows(rows=rows, decision="safe_link_candidate", limit=50, title="- top_50_safe_candidates:")
        self._print_top_rows(rows=rows, decision="needs_review", limit=50, title="- top_50_needs_review:")
        self._print_top_rows(rows=rows, decision="semantic_conflict", limit=50, title="- top_50_semantic_conflicts:")
        self.stdout.write("- blocked conflict examples:")
        for item in semantic_conflict_examples:
            self.stdout.write(f"  - {item}")
        self.stdout.write("- UTR calls=0")
        self.stdout.write("- writes=0")

    @staticmethod
    def _payload_pick(payload: dict, keys: tuple[str, ...]) -> str:
        for key in keys:
            value = str(payload.get(key) or "").strip()
            if value:
                return value
        return ""

    @staticmethod
    def _resolve_lookup_brand(*, payload_brand: str, raw_brand_name: str, product_brand_name: str) -> tuple[str, str]:
        if payload_brand:
            return payload_brand, "raw_payload.Група ТД"
        if raw_brand_name:
            return raw_brand_name, "supplier_raw_offer.brand_name"
        if product_brand_name:
            return product_brand_name, "product.brand.name"
        return "", "(empty)"

    @staticmethod
    def _resolve_lookup_article(
        *,
        supplier_code: str,
        article_source_mode: str,
        gpl_td_article: str,
        payload_article: str,
        raw_article: str,
    ) -> tuple[str, str]:
        mode = article_source_mode
        if mode == "auto":
            mode = "td_article" if supplier_code == "gpl" else "raw_article"

        if mode == "td_article":
            if gpl_td_article:
                return gpl_td_article, "raw_payload.Артикул ТД"
            if payload_article:
                return payload_article, "raw_payload.Артикул"
            if raw_article:
                return raw_article, "supplier_raw_offer.article"
            return "", "(empty)"

        if payload_article:
            return payload_article, "raw_payload.Артикул"
        if raw_article:
            return raw_article, "supplier_raw_offer.article"
        if gpl_td_article:
            return gpl_td_article, "raw_payload.Артикул ТД"
        return "", "(empty)"

    @staticmethod
    def _latest_raw_offers_map(*, supplier_code: str, product_ids: list[str]) -> dict[str, SupplierRawOffer]:
        if not product_ids:
            return {}
        rows = (
            SupplierRawOffer.objects.filter(source__code=supplier_code, matched_product_id__in=product_ids)
            .order_by("matched_product_id", "-updated_at", "-id")
            .only("id", "matched_product_id", "brand_name", "article", "product_name", "raw_payload")
        )
        out: dict[str, SupplierRawOffer] = {}
        for item in rows.iterator(chunk_size=500):
            key = str(item.matched_product_id or "")
            if key and key not in out:
                out[key] = item
        return out

    @staticmethod
    def _supplier_offer_map(*, supplier_code: str, product_ids: list[str]) -> dict[str, str]:
        if not product_ids:
            return {}
        rows = (
            SupplierOffer.objects.filter(supplier__code=supplier_code, product_id__in=product_ids)
            .order_by("product_id", "-updated_at", "-id")
            .values("id", "product_id")
        )
        out: dict[str, str] = {}
        for row in rows.iterator(chunk_size=500):
            key = str(row.get("product_id") or "")
            if key and key not in out:
                out[key] = str(row.get("id") or "")
        return out

    @staticmethod
    def _extract_image_url(*, payload: dict) -> str:
        for key in ("Зображення товару", "Фото", "image_url", "image", "photo"):
            value = str(payload.get(key) or "").strip()
            if value.startswith("http://") or value.startswith("https://"):
                return value
        return ""

    @staticmethod
    def _find_local_article_row(*, storage: AutoDbRawCloneStorage, supplier_id: int, article_number: str) -> dict:
        candidate_rows = storage.fetch_local_rows(
            table="article_numbers",
            filters={"supplierid": supplier_id, "datasupplierarticlenumber": article_number},
            limit=3,
        )
        if candidate_rows:
            return candidate_rows[0]
        fallback_rows = storage.fetch_local_rows(
            table="articles",
            filters={"supplierid": supplier_id, "datasupplierarticlenumber": article_number},
            limit=3,
        )
        if fallback_rows:
            return fallback_rows[0]
        return {}

    @staticmethod
    def _brand_match_score(*, raw_brand: str, candidate_brand: str) -> float:
        raw_norm = normalize_brand(raw_brand)
        candidate_norm = normalize_brand(candidate_brand)
        if not raw_norm or not candidate_norm:
            return 0.0
        if raw_norm == candidate_norm:
            return 1.0
        if len(raw_norm) >= 3 and (candidate_norm.startswith(raw_norm) or raw_norm.startswith(candidate_norm)):
            return 0.85
        return 0.25

    @staticmethod
    def _article_match_score(*, raw_article: str, candidate_article: str) -> float:
        raw_norm = normalize_article(raw_article)
        candidate_norm = normalize_article(candidate_article)
        if not raw_norm or not candidate_norm:
            return 0.0
        if raw_norm == candidate_norm:
            return 1.0
        if raw_norm in candidate_norm or candidate_norm in raw_norm:
            return 0.7
        return 0.15

    @staticmethod
    def _decide(
        *,
        found: bool,
        brand_match_score: float,
        article_match_score: float,
        semantic_conflicts,
        category_compatibility_score: float,
    ) -> tuple[str, str, str]:
        if not found:
            return "article_not_found", "local_autodb_article_not_found", "article_not_found"
        if brand_match_score < 0.8:
            return "brand_ambiguous", "brand_match_below_threshold", "brand_ambiguous"
        if semantic_conflicts:
            types = ",".join(sorted({item.conflict_type for item in semantic_conflicts}))
            return "semantic_conflict", f"semantic_blocker:{types}", types or "semantic_conflict"
        if article_match_score >= 0.95 and category_compatibility_score >= 0.7:
            return "safe_link_candidate", "exact_article_and_category_compatible", ""
        if category_compatibility_score < 0.7:
            return "needs_review", "category_compatibility_low", "category_compatibility_mismatch"
        return "needs_review", "partial_match_requires_manual_review", "needs_review"

    def _print_top_rows(self, *, rows: list[dict[str, str]], decision: str, limit: int, title: str) -> None:
        filtered = [row for row in rows if row.get("decision") == decision][:limit]
        self.stdout.write(title)
        for row in filtered:
            self.stdout.write(
                "  - "
                f"{row.get('product_id')} | {row.get('raw_brand')} {row.get('raw_article')} | "
                f"{row.get('raw_category')} -> {row.get('mapped_site_category')} | "
                f"a={row.get('article_match_score')} b={row.get('brand_match_score')} "
                f"s={row.get('semantic_score')} c={row.get('category_compatibility_score')} | "
                f"{row.get('reason')}"
            )

    @staticmethod
    def _export_csv(*, path: str, rows: list[dict[str, str]]) -> None:
        output = Path(path).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        headers = [
            "product_id",
            "supplier_raw_offer_id",
            "supplier_offer_id",
            "raw_brand_source_field",
            "raw_brand",
            "article_source_field",
            "lookup_article",
            "raw_article",
            "gpl_code",
            "gpl_article",
            "gpl_td_article",
            "raw_name",
            "raw_category",
            "raw_group",
            "mapped_site_category",
            "gpl_image_url",
            "candidate_autodb_supplier_id",
            "candidate_autodb_article_number",
            "candidate_autodb_title",
            "candidate_autodb_group",
            "brand_match_score",
            "article_match_score",
            "semantic_score",
            "category_compatibility_score",
            "decision",
            "reason",
            "blocker_type",
        ]
        with output.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
