from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.autodb.services.article_number_normalizer import ArticleNumberNormalizer
from apps.autodb.services.column_helpers import find_column_name, find_value
from apps.autodb.services.local_db_readiness import wait_for_local_autodb_ready
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.autodb.services.raw_offer_enrichment import AutoDbRawOfferEnrichmentService, PairBucket, PairResolution
from apps.catalog.models import AutoDbProductLinkQuality, Product
from apps.catalog.services.product_management import get_product_display_name
from apps.compatibility.models import ProductFitment
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _brand_hint_key(value: str) -> str:
    return re.sub(r"[\W_]+", "", str(value or "").strip().upper(), flags=re.UNICODE)


def _tokenize(text: str) -> set[str]:
    return {
        item
        for item in re.split(r"[^A-Za-zА-Яа-яІіЇїЄєҐґ0-9]+", str(text or "").lower())
        if len(item) >= 3
    }


@dataclass
class InheritedAuditRow:
    raw_offer_id: str
    supplier: str
    raw_brand: str
    raw_article: str
    raw_product_name: str
    matched_product_id: str
    matched_product_display_name: str
    inherited_autodb_article_key: str
    autodb_title: str
    autodb_category: str
    link_quality_status: str
    suspicious_status: str
    recommendation: str
    reason: str
    risk_score: int
    confidence: float
    fitments_excluded_count: int


class Command(BaseCommand):
    help = "Read-only audit for inherited link opportunities from matched products."

    NON_AUTO_BRAND_HINTS = {
        _brand_hint_key("CS SYSTEM"): "CS SYSTEM",
        _brand_hint_key("MR.BUILD"): "Mr.Build",
        _brand_hint_key("MR BUILD"): "Mr.Build",
        _brand_hint_key("NOVOABRASIVE"): "NOVOABRASIVE",
        _brand_hint_key("VIRA"): "VIRA",
        _brand_hint_key("K2"): "K2",
        _brand_hint_key("Без бренду"): "Без бренду",
        _brand_hint_key("ТМК"): "ТМК",
    }

    FOCUSED_CASES = (
        ("LSA", "411124", "300:820099"),
        ("MITKA", "MII107", "300:820099"),
        ("WIX FILTERS", "325193", "324:WL7042"),
    )
    PART_TYPE_TOKENS = {
        "фільтр",
        "фильтр",
        "filter",
        "колодки",
        "тормозные",
        "гальмівні",
        "ремкомплект",
        "kit",
        "амортизатор",
        "shock",
        "свеча",
        "свічка",
        "plug",
        "bearing",
        "підшипник",
        "подшипник",
        "рычаг",
        "важіль",
    }
    CONFLICT_TOKENS = {
        "емаль",
        "эмаль",
        "аерозоль",
        "аэрозоль",
        "paint",
        "лаки",
        "очисник",
        "очиститель",
    }

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, default="", help="Supplier/source code, e.g. GPL")
        parser.add_argument("--limit", type=int, default=1000, help="Limit raw offers to audit")
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV path")
        parser.add_argument("--wait-for-autodb", type=int, default=0, help="Wait up to N seconds for local Auto_DB_Pro readiness")

    def handle(self, *args, **options):
        supplier_code = str(options.get("supplier") or "").strip().lower()
        limit = max(int(options.get("limit") or 0), 0)
        export_csv = str(options.get("export_csv") or "").strip()
        wait_for_autodb = max(int(options.get("wait_for_autodb") or 0), 0)

        if not supplier_code:
            raise CommandError("Provide --supplier CODE.")

        readiness = wait_for_local_autodb_ready(timeout_seconds=wait_for_autodb, interval_seconds=2.0)
        if not readiness.ready:
            raise CommandError(
                "Auto_DB_Pro local DB is not ready/recovering. "
                f"host={readiness.host} port={readiness.port} database={readiness.database} reason={readiness.reason}"
            )

        self.stdout.write(
            "Auto_DB_Pro inherited-link audit started "
            f"supplier={supplier_code} limit={limit or 'none'} mode=read-only"
        )

        offers = self._build_queryset(supplier_code=supplier_code, limit=limit)
        inherited_rows = self._audit_inherited_offers(offers=offers)

        self._print_summary(inherited_rows)
        self._print_suspicious_summary(inherited_rows)
        self._print_rows(inherited_rows)
        self._print_examples(inherited_rows, recommendation="can_inherit_high_confidence", top_n=20)
        self._print_examples(inherited_rows, recommendation="can_inherit_medium_confidence", top_n=20)
        self._print_examples(inherited_rows, recommendation="needs_manual_review", top_n=20)
        self._print_focused_cases(supplier_code=supplier_code)

        if export_csv:
            self._export_csv(export_csv, inherited_rows)
            self.stdout.write(f"CSV export: {export_csv}")

        self.stdout.write("- report_mode: read-only (no Product/SupplierRawOffer writes)")
        self.stdout.write("- UTR calls: 0")
        self.stdout.write("- price/stock changed: 0")

    def _build_queryset(self, *, supplier_code: str, limit: int) -> list[SupplierRawOffer]:
        qs = (
            SupplierRawOffer.objects.select_related("source", "supplier", "matched_product", "matched_product__brand", "matched_product__category")
            .filter(Q(source__code__iexact=supplier_code) | Q(supplier__code__iexact=supplier_code))
            .exclude(matched_product_id__isnull=True)
            .exclude(matched_product__autodb_article_key="")
            .order_by("id")
        )
        if limit > 0:
            qs = qs[:limit]
        return list(qs)

    def _audit_inherited_offers(self, *, offers: list[SupplierRawOffer]) -> list[InheritedAuditRow]:
        normalizer = ArticleNumberNormalizer()
        pair_to_offers: dict[tuple[str, str], list[SupplierRawOffer]] = defaultdict(list)

        for offer in offers:
            raw_brand = str(offer.brand_name or "").strip()
            raw_article = str(offer.article or offer.external_sku or "").strip()
            norm_brand = str(offer.normalized_brand or "").strip() or normalize_brand(raw_brand)
            article_norm = normalizer.normalize(raw_article)
            norm_article = str(offer.normalized_article or "").strip() or article_norm.normalized
            if not norm_brand or not norm_article:
                continue
            pair_to_offers[(norm_brand, norm_article)].append(offer)

        buckets = [
            PairBucket(
                normalized_brand=key[0],
                normalized_article=key[1],
                sample_brand=str(items[0].brand_name or key[0]),
                sample_article=str(items[0].article or items[0].external_sku or key[1]),
                article_variants=normalizer.normalize(str(items[0].article or items[0].external_sku or key[1])).search_variants or (key[1],),
                source_id=str(items[0].source_id) if items[0].source_id else None,
                supplier_id=str(items[0].supplier_id) if items[0].supplier_id else None,
                offer_count=len(items),
                matched_product_ids={str(item.matched_product_id) for item in items if item.matched_product_id},
            )
            for key, items in pair_to_offers.items()
        ]

        service = AutoDbRawOfferEnrichmentService()
        unresolved_keys: set[tuple[str, str]] = set()
        for chunk in [buckets[idx : idx + 500] for idx in range(0, len(buckets), 500)]:
            resolved = service._resolve_local_chunk(chunk)
            for item in resolved:
                key = (item.bucket.normalized_brand, item.bucket.normalized_article)
                if not item.article_key:
                    unresolved_keys.add(key)

        quality_map, excluded_fitments_map = self._build_quality_maps(offers=offers)
        context_cache: dict[str, dict[str, str]] = {}
        rows: list[InheritedAuditRow] = []
        for key, key_offers in pair_to_offers.items():
            if key not in unresolved_keys:
                continue
            for offer in key_offers:
                row = self._build_audit_row(
                    offer=offer,
                    quality_map=quality_map,
                    excluded_fitments_map=excluded_fitments_map,
                    context_cache=context_cache,
                )
                rows.append(row)

        rows.sort(key=lambda item: (item.recommendation, -item.risk_score, item.raw_brand, item.raw_article))
        return rows

    def _build_quality_maps(self, *, offers: list[SupplierRawOffer]) -> tuple[dict[tuple[str, str], str], dict[tuple[str, str], int]]:
        product_ids = {str(item.matched_product_id) for item in offers if item.matched_product_id}
        if not product_ids:
            return {}, {}

        quality_rows = AutoDbProductLinkQuality.objects.filter(product_id__in=product_ids).values("product_id", "autodb_article_key", "status")
        quality_map = {
            (str(row["product_id"]), str(row["autodb_article_key"] or "").strip()): str(row["status"] or "")
            for row in quality_rows
        }

        fitment_rows = (
            ProductFitment.objects.filter(product_id__in=product_ids, excluded_from_public_filtering=True)
            .values("product_id", "autodb_article_key")
        )
        excluded_map: Counter[tuple[str, str]] = Counter()
        for row in fitment_rows:
            excluded_map[(str(row["product_id"]), str(row.get("autodb_article_key") or "").strip())] += 1
        return quality_map, dict(excluded_map)

    def _build_audit_row(
        self,
        *,
        offer: SupplierRawOffer,
        quality_map: dict[tuple[str, str], str],
        excluded_fitments_map: dict[tuple[str, str], int],
        context_cache: dict[str, dict[str, str]],
    ) -> InheritedAuditRow:
        product = offer.matched_product
        product_id = str(product.id)
        article_key = str(product.autodb_article_key or "").strip()
        key_tuple = (product_id, article_key)

        quality_status = quality_map.get(key_tuple, "unknown")
        fitment_excluded_count = int(excluded_fitments_map.get(key_tuple, 0))
        suspicious_status = "yes" if (quality_status == AutoDbProductLinkQuality.STATUS_SUSPICIOUS or fitment_excluded_count > 0) else "no"

        context = context_cache.get(article_key)
        if context is None:
            context = self._lookup_autodb_context(product=product)
            context_cache[article_key] = context
        raw_product_name = str(offer.product_name or "").strip()
        raw_article = str(offer.article or "").strip()
        raw_external_sku = str(offer.external_sku or "").strip()
        product_display = get_product_display_name(product, "uk")
        inherited_article_number = self._parse_inherited_article_number(article_key=article_key, fallback=getattr(product, "autodb_article_number", ""))
        recommendation, reason, risk = self._recommendation(
            raw_brand=str(offer.brand_name or "").strip(),
            raw_article=raw_article,
            raw_external_sku=raw_external_sku,
            raw_product_name=raw_product_name,
            product_display=product_display,
            autodb_title=context["autodb_title"],
            autodb_category=context["autodb_category"],
            inherited_article_number=inherited_article_number,
            product_brand=str(getattr(getattr(product, "brand", None), "name", "") or ""),
            quality_status=quality_status,
            suspicious_status=suspicious_status,
        )
        confidence = self._confidence_from_recommendation(recommendation=recommendation, reason=reason)
        if fitment_excluded_count > 0 and recommendation != "suspicious_do_not_inherit":
            recommendation = "suspicious_do_not_inherit"
            reason = f"fitments_excluded_from_public_filtering={fitment_excluded_count}"
            risk = max(risk, 85)
            confidence = 0.0

        return InheritedAuditRow(
            raw_offer_id=str(offer.id),
            supplier=str(getattr(offer.supplier, "code", "") or getattr(offer.source, "code", "") or "-").lower(),
            raw_brand=str(offer.brand_name or "").strip(),
            raw_article=str(offer.article or offer.external_sku or "").strip(),
            raw_product_name=raw_product_name,
            matched_product_id=product_id,
            matched_product_display_name=product_display,
            inherited_autodb_article_key=article_key,
            autodb_title=context["autodb_title"],
            autodb_category=context["autodb_category"],
            link_quality_status=quality_status,
            suspicious_status=suspicious_status,
            recommendation=recommendation,
            reason=reason,
            risk_score=risk,
            confidence=confidence,
            fitments_excluded_count=fitment_excluded_count,
        )

    def _recommendation(
        self,
        *,
        raw_brand: str,
        raw_article: str,
        raw_external_sku: str,
        raw_product_name: str,
        product_display: str,
        autodb_title: str,
        autodb_category: str,
        inherited_article_number: str,
        product_brand: str,
        quality_status: str,
        suspicious_status: str,
    ) -> tuple[str, str, int]:
        if suspicious_status == "yes" or quality_status == AutoDbProductLinkQuality.STATUS_SUSPICIOUS:
            return "suspicious_do_not_inherit", "product_link_quality_is_suspicious", 95

        if _brand_hint_key(raw_brand) in self.NON_AUTO_BRAND_HINTS:
            return "non_auto_ignore", "brand_marked_as_supplier_only_or_non_auto", 80

        raw_blob = " ".join(item for item in [raw_product_name, raw_article, raw_external_sku] if item).strip()
        article_evidence_reason = self._article_evidence_reason(
            inherited_article_number=inherited_article_number,
            raw_name=raw_product_name,
            raw_article=raw_article,
            raw_external_sku=raw_external_sku,
            raw_brand=raw_brand,
            raw_blob=raw_blob,
        )
        brand_match = normalize_brand(raw_brand) == normalize_brand(product_brand) if raw_brand and product_brand else True

        raw_part_tokens = self._part_type_tokens(raw_product_name)
        product_part_tokens = self._part_type_tokens(product_display)
        autodb_part_tokens = self._part_type_tokens(" ".join([autodb_title, autodb_category]).strip())
        part_overlap_product = raw_part_tokens & product_part_tokens
        part_overlap_autodb = raw_part_tokens & autodb_part_tokens

        has_conflict_tokens = bool(_tokenize(raw_product_name) & self.CONFLICT_TOKENS)
        autodb_joint_tokens = bool(_tokenize(" ".join([autodb_title, autodb_category])) & {"шарнир", "joint", "комплект", "kit"})
        if has_conflict_tokens and autodb_joint_tokens and not article_evidence_reason:
            return "needs_manual_review", "semantic_conflict_supplier_non_part_vs_autodb_part", 75

        if article_evidence_reason and brand_match:
            return "can_inherit_high_confidence", article_evidence_reason, 15

        if article_evidence_reason and not brand_match:
            return "can_inherit_medium_confidence", f"{article_evidence_reason};brand_mismatch", 35

        raw_tokens = _tokenize(raw_product_name)
        comparison_tokens = _tokenize(f"{product_display} {autodb_title} {autodb_category}")
        if raw_tokens:
            overlap = len(raw_tokens & comparison_tokens) / max(len(raw_tokens), 1)
            if overlap >= 0.35 and (part_overlap_product or part_overlap_autodb) and brand_match:
                return "can_inherit_medium_confidence", f"token_overlap={overlap:.2f};part_type_overlap", 45
            return "needs_manual_review", f"low_token_overlap={overlap:.2f}", 60

        return "needs_manual_review", "missing_raw_product_name_for_confidence", 55

    def _confidence_from_recommendation(self, *, recommendation: str, reason: str) -> float:
        if recommendation == "can_inherit_high_confidence":
            if reason.startswith("article_number_in_article_field") or reason.startswith("article_number_in_external_sku"):
                return 1.0
            return 0.95
        if recommendation == "can_inherit_medium_confidence":
            return 0.65
        return 0.0

    def _parse_inherited_article_number(self, *, article_key: str, fallback: Any) -> str:
        key = str(article_key or "").strip()
        if ":" in key:
            _, suffix = key.split(":", 1)
            if str(suffix).strip():
                return str(suffix).strip()
        return str(fallback or "").strip()

    def _normalize_text_for_article(self, value: str) -> str:
        return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())

    def _article_variants(self, article_number: str) -> set[str]:
        base = str(article_number or "").strip().upper()
        if not base:
            return set()
        normalized = self._normalize_text_for_article(base)
        variants = {base, normalized}
        m = re.match(r"^([A-Z]+)([0-9]+)$", normalized)
        if m:
            letters, digits = m.groups()
            variants.add(f"{letters} {digits}")
            variants.add(f"{letters}-{digits}")
            variants.add(f"{letters}/{digits}")
            # numeric-tail fallback is accepted only with extra brand/part evidence.
            if len(digits) >= 4:
                variants.add(digits)
        return {item for item in variants if item}

    def _contains_variant(self, *, raw_text: str, variant: str) -> bool:
        if not raw_text or not variant:
            return False
        text_norm = self._normalize_text_for_article(raw_text)
        var_norm = self._normalize_text_for_article(variant)
        if not var_norm:
            return False
        if var_norm.isdigit():
            return False
        return var_norm in text_norm

    def _part_type_tokens(self, text: str) -> set[str]:
        return {token for token in _tokenize(text) if token in self.PART_TYPE_TOKENS}

    def _article_evidence_reason(
        self,
        *,
        inherited_article_number: str,
        raw_name: str,
        raw_article: str,
        raw_external_sku: str,
        raw_brand: str,
        raw_blob: str,
    ) -> str:
        variants = self._article_variants(inherited_article_number)
        if not variants:
            return ""

        for variant in variants:
            if self._contains_variant(raw_text=raw_article, variant=variant):
                return "article_number_in_article_field"
        for variant in variants:
            if self._contains_variant(raw_text=raw_external_sku, variant=variant):
                return "article_number_in_external_sku"
        for variant in variants:
            if self._contains_variant(raw_text=raw_name, variant=variant):
                return "article_number_in_raw_name"

        # numeric-tail fallback only when brand and part-type context exist in raw name.
        raw_name_tokens = _tokenize(raw_name)
        has_part_context = bool(raw_name_tokens & self.PART_TYPE_TOKENS)
        has_brand_context = bool(normalize_brand(raw_brand or "") and normalize_brand(raw_brand or "") in self._normalize_text_for_article(raw_blob))
        for variant in variants:
            if variant.isdigit() and variant in self._normalize_text_for_article(raw_name) and has_part_context and has_brand_context:
                return "article_number_numeric_tail_in_raw_name_with_context"
        return ""

    def _lookup_autodb_context(self, *, product: Product) -> dict[str, str]:
        supplier_id = _safe_int(getattr(product, "autodb_supplier_id", None))
        article_number = str(getattr(product, "autodb_article_number", "") or "").strip()
        if (not supplier_id or not article_number) and str(getattr(product, "autodb_article_key", "") or ""):
            key = str(product.autodb_article_key)
            if ":" in key:
                prefix, suffix = key.split(":", 1)
                supplier_id = supplier_id or _safe_int(prefix)
                article_number = article_number or str(suffix or "").strip()

        storage = AutoDbRawCloneStorage()
        autodb_title = self._resolve_article_title(storage=storage, supplier_id=supplier_id, article_number=article_number)
        autodb_category = self._resolve_prd_title(storage=storage, supplier_id=supplier_id, article_number=article_number)
        return {
            "autodb_title": autodb_title,
            "autodb_category": autodb_category,
        }

    def _resolve_article_title(self, *, storage: AutoDbRawCloneStorage, supplier_id: int | None, article_number: str) -> str:
        if supplier_id is None or supplier_id <= 0 or not article_number:
            return ""
        columns = list(storage.get_local_columns("articles"))
        if not columns:
            return ""
        supplier_col = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id"])
        article_col = find_column_name(columns, ["DataSupplierArticleNumber", "datasupplierarticlenumber", "article", "articlenumber", "number"])
        if not supplier_col or not article_col:
            return ""
        rows = storage.fetch_local_rows(
            table="articles",
            filters={supplier_col: supplier_id, article_col: article_number},
            limit=1,
            columns=columns,
        )
        if not rows:
            return ""
        row = rows[0]
        for key in ["normalizeddescription", "NormalizedDescription", "description", "Description"]:
            value = str(find_value(row, [key]) or "").strip()
            if value:
                return value[:255]
        return ""

    def _resolve_prd_title(self, *, storage: AutoDbRawCloneStorage, supplier_id: int | None, article_number: str) -> str:
        if supplier_id is None or supplier_id <= 0 or not article_number:
            return ""
        product_ids = self._find_product_ids(storage=storage, table="article_prd", supplier_id=supplier_id, article_number=article_number)
        if not product_ids:
            product_ids = self._find_product_ids(storage=storage, table="article_links", supplier_id=supplier_id, article_number=article_number)
        if not product_ids:
            return ""

        prd_columns = list(storage.get_local_columns("prd"))
        if not prd_columns:
            return ""
        id_col = find_column_name(prd_columns, ["id", "productid", "ProductId", "prdid", "prdId"])
        if not id_col:
            return ""
        prd_rows = storage.fetch_local_rows_in(
            table="prd",
            column=id_col,
            values=product_ids,
            limit=max(100, len(product_ids) * 2),
            columns=prd_columns,
        )
        for row in prd_rows:
            for key in ["fulldescription", "fullDescription", "normalizeddescription", "NormalizedDescription", "description", "Description"]:
                value = str(find_value(row, [key]) or "").strip()
                if value:
                    return value[:255]
        return ""

    def _find_product_ids(self, *, storage: AutoDbRawCloneStorage, table: str, supplier_id: int, article_number: str) -> list[int]:
        columns = list(storage.get_local_columns(table))
        if not columns:
            return []
        supplier_col = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id"])
        article_col = find_column_name(columns, ["DataSupplierArticleNumber", "datasupplierarticlenumber", "article", "articlenumber", "number"])
        if not supplier_col or not article_col:
            return []
        rows = storage.fetch_local_rows(
            table=table,
            filters={supplier_col: supplier_id, article_col: article_number},
            limit=500,
            columns=columns,
        )
        product_ids: list[int] = []
        for row in rows:
            prd_id = _safe_int(find_value(row, ["productId", "productid", "ProductId", "prdid", "prdId", "id"]))
            if prd_id is None or prd_id in product_ids:
                continue
            product_ids.append(prd_id)
        return product_ids

    def _print_summary(self, rows: list[InheritedAuditRow]):
        pair_keys = {(item.raw_brand, item.raw_article) for item in rows}
        product_ids = {item.matched_product_id for item in rows}
        rec_counter = Counter(item.recommendation for item in rows)
        blocked_by_suspicious = sum(1 for item in rows if item.recommendation == "suspicious_do_not_inherit")

        can_high_brand = Counter(item.raw_brand or "-" for item in rows if item.recommendation == "can_inherit_high_confidence")
        can_medium_brand = Counter(item.raw_brand or "-" for item in rows if item.recommendation == "can_inherit_medium_confidence")
        manual_brand = Counter(item.raw_brand or "-" for item in rows if item.recommendation == "needs_manual_review")

        self.stdout.write("Inherited opportunities audit summary:")
        self.stdout.write(f"- total inherited opportunities: {len(rows)}")
        self.stdout.write(f"- unique pairs: {len(pair_keys)}")
        self.stdout.write(f"- unique products: {len(product_ids)}")
        self.stdout.write(f"- high_confidence_can_inherit: {rec_counter.get('can_inherit_high_confidence', 0)}")
        self.stdout.write(f"- medium_confidence_can_inherit: {rec_counter.get('can_inherit_medium_confidence', 0)}")
        self.stdout.write(f"- needs_manual_review: {rec_counter.get('needs_manual_review', 0)}")
        self.stdout.write(f"- suspicious_do_not_inherit: {rec_counter.get('suspicious_do_not_inherit', 0)}")
        self.stdout.write(f"- blocked_by_suspicious_quality: {blocked_by_suspicious}")
        self.stdout.write(f"- non_auto_ignore: {rec_counter.get('non_auto_ignore', 0)}")

        self.stdout.write("Top brands by high_confidence_can_inherit:")
        for brand, count in can_high_brand.most_common(20):
            self.stdout.write(f"- {brand}: {count}")

        self.stdout.write("Top brands by medium_confidence_can_inherit:")
        for brand, count in can_medium_brand.most_common(20):
            self.stdout.write(f"- {brand}: {count}")

        self.stdout.write("Top brands by needs_manual_review:")
        for brand, count in manual_brand.most_common(20):
            self.stdout.write(f"- {brand}: {count}")

    def _print_examples(self, rows: list[InheritedAuditRow], *, recommendation: str, top_n: int):
        if recommendation == "can_inherit_high_confidence":
            title = "Examples can_inherit_high_confidence:"
        elif recommendation == "can_inherit_medium_confidence":
            title = "Examples can_inherit_medium_confidence:"
        else:
            title = "Examples needs_manual_review:"
        self.stdout.write(title)
        selected = [item for item in rows if item.recommendation == recommendation][:top_n]
        for item in selected:
            self.stdout.write(
                f"- raw_offer_id={item.raw_offer_id} brand={item.raw_brand or '-'} article={item.raw_article or '-'} "
                f"product={item.matched_product_id} key={item.inherited_autodb_article_key} "
                f"display_name={item.matched_product_display_name or '-'} autodb_title={item.autodb_title or '-'} "
                f"category={item.autodb_category or '-'} quality={item.link_quality_status or '-'} "
                f"suspicious={item.suspicious_status} confidence={item.confidence:.2f} reason={item.reason}"
            )

    def _print_suspicious_summary(self, rows: list[InheritedAuditRow]):
        suspicious_rows = [item for item in rows if item.suspicious_status == "yes"]
        suspicious_products = {item.matched_product_id for item in suspicious_rows}
        fitments_excluded = sum(item.fitments_excluded_count for item in suspicious_rows)

        self.stdout.write("Suspicious links summary:")
        self.stdout.write(f"- count products: {len(suspicious_products)}")
        self.stdout.write(f"- count raw offers affected: {len(suspicious_rows)}")
        self.stdout.write(f"- count fitments excluded: {fitments_excluded}")
        for item in suspicious_rows[:20]:
            self.stdout.write(
                f"- raw_offer_id={item.raw_offer_id} product={item.matched_product_id} "
                f"key={item.inherited_autodb_article_key or '-'} link_quality_status={item.link_quality_status or '-'} "
                f"excluded_from_public_filtering={'yes' if item.fitments_excluded_count > 0 else 'no'} "
                f"recommendation={item.recommendation} reason={item.reason}"
            )

    def _print_rows(self, rows: list[InheritedAuditRow]):
        self.stdout.write("Inherited opportunities rows:")
        for item in rows:
            self.stdout.write(
                f"- raw_offer_id={item.raw_offer_id} supplier={item.supplier} "
                f"raw_brand={item.raw_brand or '-'} raw_article={item.raw_article or '-'} "
                f"raw_product_name={item.raw_product_name or '-'} matched_product_id={item.matched_product_id} "
                f"matched_product_display_name={item.matched_product_display_name or '-'} "
                f"matched_product_autodb_article_key={item.inherited_autodb_article_key or '-'} "
                f"autodb_article_title={item.autodb_title or '-'} autodb_category={item.autodb_category or '-'} "
                f"link_quality_status={item.link_quality_status or '-'} suspicious={item.suspicious_status} "
                f"recommendation={item.recommendation} confidence={item.confidence:.2f} reason={item.reason} risk_score={item.risk_score}"
            )

    def _print_focused_cases(self, *, supplier_code: str):
        self.stdout.write("Focused risky examples:")
        for raw_brand, raw_article, expected_key in self.FOCUSED_CASES:
            brand_norm = normalize_brand(raw_brand)
            article_norm = normalize_article(raw_article)
            offer = (
                SupplierRawOffer.objects.select_related("matched_product", "matched_product__brand", "matched_product__category", "supplier", "source")
                .filter(Q(source__code__iexact=supplier_code) | Q(supplier__code__iexact=supplier_code))
                .exclude(matched_product_id__isnull=True)
                .exclude(matched_product__autodb_article_key="")
                .filter(
                    Q(normalized_brand__iexact=brand_norm) | Q(brand_name__iexact=raw_brand),
                    Q(normalized_article__iexact=article_norm) | Q(article__iexact=raw_article),
                )
                .filter(matched_product__autodb_article_key=expected_key)
                .order_by("id")
                .first()
            )
            if not offer:
                offer = (
                    SupplierRawOffer.objects.select_related(
                        "matched_product",
                        "matched_product__brand",
                        "matched_product__category",
                        "supplier",
                        "source",
                    )
                    .filter(Q(source__code__iexact=supplier_code) | Q(supplier__code__iexact=supplier_code))
                    .exclude(matched_product_id__isnull=True)
                    .exclude(matched_product__autodb_article_key="")
                    .filter(
                        Q(normalized_brand__iexact=brand_norm) | Q(brand_name__iexact=raw_brand),
                        Q(normalized_article__iexact=article_norm) | Q(article__iexact=raw_article),
                    )
                    .order_by("id")
                    .first()
                )
            if not offer:
                self.stdout.write(f"- {raw_brand} / {raw_article}: not found in current supplier scope")
                continue

            quality_map, excluded_map = self._build_quality_maps(offers=[offer])
            row = self._build_audit_row(
                offer=offer,
                quality_map=quality_map,
                excluded_fitments_map=excluded_map,
                context_cache={},
            )
            self.stdout.write(f"- {raw_brand} / {raw_article} / expected_key={expected_key}:")
            self.stdout.write(f"- product_display_name={row.matched_product_display_name or '-'}")
            self.stdout.write(f"- raw_offer_name={row.raw_product_name or '-'}")
            self.stdout.write(f"- matched_product_autodb_article_key={row.inherited_autodb_article_key or '-'}")
            self.stdout.write(f"- autodb_title={row.autodb_title or '-'}")
            self.stdout.write(f"- autodb_category={row.autodb_category or '-'}")
            self.stdout.write(f"- recommendation={row.recommendation}")
            self.stdout.write(f"- confidence={row.confidence:.2f}")
            self.stdout.write(f"- reason={row.reason}")

    def _export_csv(self, path: str, rows: list[InheritedAuditRow]):
        export_path = Path(path).expanduser()
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with export_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "supplier",
                    "raw_brand",
                    "raw_article",
                    "raw_product_name",
                    "matched_product_id",
                    "matched_product_display_name",
                    "inherited_autodb_article_key",
                    "autodb_title",
                    "autodb_category",
                    "link_quality_status",
                    "risk_score",
                    "confidence",
                    "recommendation",
                    "reason",
                    "sample_raw_offer_id",
                ],
            )
            writer.writeheader()
            for item in rows:
                writer.writerow(
                    {
                        "supplier": item.supplier,
                        "raw_brand": item.raw_brand,
                        "raw_article": item.raw_article,
                        "raw_product_name": item.raw_product_name,
                        "matched_product_id": item.matched_product_id,
                        "matched_product_display_name": item.matched_product_display_name,
                        "inherited_autodb_article_key": item.inherited_autodb_article_key,
                        "autodb_title": item.autodb_title,
                        "autodb_category": item.autodb_category,
                        "link_quality_status": item.link_quality_status,
                        "risk_score": item.risk_score,
                        "confidence": f"{item.confidence:.2f}",
                        "recommendation": item.recommendation,
                        "reason": item.reason,
                        "sample_raw_offer_id": item.raw_offer_id,
                    }
                )
