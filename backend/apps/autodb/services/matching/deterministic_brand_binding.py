from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.db import OperationalError, ProgrammingError, connections, transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.autodb.models import AutoDbSupplierBrandAlias
from apps.autodb.services.matching.brand_coverage import AutoDbBrandCoverageAuditService
from apps.autodb.services.matching.constants import NON_TECDOC_BRAND_KEYS, UNSAFE_BRAND_KEYS
from apps.autodb.services.matching.job_builder import AutoDbMatchJobBuilder
from apps.autodb.services.matching.reports import write_report
from apps.catalog.models import AutoDbProductLinkQuality, Brand, Product, ProductAttribute, ProductImage
from apps.compatibility.models import ProductFitment
from apps.pricing.models import ProductPrice, SupplierOffer
from apps.supplier_imports.parsers.utils import normalize_brand
from apps.supplier_imports.models import SupplierBrandAlias


REQUESTED_BRANDS = [
    "LEMFORDER",
    "LEMFOERDER",
    "LEMFÖRDER",
    "LESJOFORS",
    "LESJOEFORS",
    "LESJÖFORS",
    "LOBRO",
    "LOEBRO",
    "LÖBRO",
    "NURAL",
    "NUERAL",
    "NÜRAL",
    "DURER",
    "DÜRER",
    "EBERSPACHER",
    "EBERSPAECHER",
    "EBERSPÄCHER",
    "KALE OTO RADYATOR",
    "KALE OTO RADYATÖR",
    "MALO",
    "MALÒ",
    "MALÓ",
    "MALÖ",
    "NEOLUX",
    "NEOLUX R",
    "NEOLUX ®",
    "NEOLUX®",
    "SCHLUTTER TURBOLADER",
    "SCHLUETTER TURBOLADER",
    "SCHLÜTTER TURBOLADER",
    "SPAHN GLUHLAMPEN",
    "SPAHN GLUEHLAMPEN",
    "SPAHN GLÜHLAMPEN",
]


@dataclass(frozen=True)
class SupplierEntry:
    supplier_id: int
    description: str
    matchcode: str
    nbrofarticles: int
    variants: tuple[str, ...]


@dataclass(frozen=True)
class BrandCandidate:
    catalog_brand_id: str
    catalog_brand_name: str
    normalized_catalog_brand: str
    generated_catalog_variants: str
    autodb_supplier_id: str
    autodb_supplier_description: str
    autodb_supplier_matchcode: str
    generated_supplier_variants: str
    match_reason: str
    product_count: int
    products_missing_autodb_supplier_id: int
    products_existing_same_supplier: int
    products_existing_different_supplier: int
    manually_locked_count: int
    decision: str
    confidence: str
    reason: str
    sample_skus: str


class DeterministicBrandNormalizer:
    _REMOVE_TM_RE = re.compile(r"\(\s*R\s*\)", flags=re.IGNORECASE)
    _PUNCT_RE = re.compile(r"[\-\.,/\\\[\]\(\){}'`\"|:;]+")
    _SPACE_RE = re.compile(r"\s+")

    _GERMAN = {
        "Ä": ("A", "AE"),
        "Ö": ("O", "OE"),
        "Ü": ("U", "UE"),
        "ẞ": ("SS",),
        "ß": ("SS",),
    }

    _DIRECT = {
        "Á": "A", "À": "A", "Â": "A", "Ã": "A", "Å": "A", "Ā": "A", "Ă": "A", "Ą": "A",
        "á": "A", "à": "A", "â": "A", "ã": "A", "å": "A", "ā": "A", "ă": "A", "ą": "A",
        "É": "E", "È": "E", "Ê": "E", "Ë": "E", "Ē": "E", "Ė": "E", "Ę": "E",
        "é": "E", "è": "E", "ê": "E", "ë": "E", "ē": "E", "ė": "E", "ę": "E",
        "Í": "I", "Ì": "I", "Î": "I", "Ï": "I", "Ī": "I", "Į": "I",
        "í": "I", "ì": "I", "î": "I", "ï": "I", "ī": "I", "į": "I",
        "Ó": "O", "Ò": "O", "Ô": "O", "Õ": "O", "Ō": "O", "Ø": "O",
        "ó": "O", "ò": "O", "ô": "O", "õ": "O", "ō": "O", "ø": "O",
        "Ú": "U", "Ù": "U", "Û": "U", "Ū": "U",
        "ú": "U", "ù": "U", "û": "U", "ū": "U",
        "Ç": "C", "ç": "C", "Ñ": "N", "ñ": "N",
        "Ş": "S", "ş": "S", "Š": "S", "š": "S",
        "Ž": "Z", "ž": "Z", "Ź": "Z", "ź": "Z", "Ż": "Z", "ż": "Z",
        "İ": "I", "ı": "I",
    }

    def variants(self, value: str) -> set[str]:
        raw = str(value or "").strip()
        if not raw:
            return set()
        prepared = self._prepare_inputs(raw)
        out: set[str] = set()
        for item in prepared:
            for variant in self._expand_chars(item):
                normalized = normalize_brand(variant)
                if normalized:
                    out.add(normalized)
                no_tm = self._drop_trailing_tm_r(variant)
                normalized_no_tm = normalize_brand(no_tm)
                if normalized_no_tm:
                    out.add(normalized_no_tm)
        return out

    def _prepare_inputs(self, raw: str) -> set[str]:
        candidates = {raw}
        tm_clean = raw.replace("®", " ").replace("™", " ").replace("©", " ")
        tm_clean = self._REMOVE_TM_RE.sub(" ", tm_clean)
        tm_clean = self._PUNCT_RE.sub(" ", tm_clean)
        tm_clean = self._SPACE_RE.sub(" ", tm_clean).strip()
        if tm_clean:
            candidates.add(tm_clean)
        return candidates

    def _expand_chars(self, value: str) -> set[str]:
        options = [""]
        for char in value:
            replacements = self._char_replacements(char)
            next_options: list[str] = []
            for prefix in options:
                for replacement in replacements:
                    next_options.append(prefix + replacement)
            options = next_options
            if len(options) > 256:
                options = options[:256]
        return {item for item in options if item}

    def _char_replacements(self, char: str) -> tuple[str, ...]:
        if char in self._GERMAN:
            return self._GERMAN[char]
        if char in self._DIRECT:
            return (self._DIRECT[char],)
        upper = char.upper()
        if "A" <= upper <= "Z" or "0" <= upper <= "9":
            return (upper,)
        if char.isspace() or char in "-.,/\\[](){}'`\"|:;":
            return ("",)
        folded = unicodedata.normalize("NFKD", char)
        folded_ascii = "".join(item for item in folded if not unicodedata.combining(item))
        folded_upper = folded_ascii.upper()
        folded_norm = normalize_brand(folded_upper)
        if folded_norm:
            return (folded_norm,)
        return ("",)

    def _drop_trailing_tm_r(self, value: str) -> str:
        tokens = [item for item in re.split(r"\s+", value.strip()) if item]
        if len(tokens) >= 2 and tokens[-1].upper() == "R":
            return " ".join(tokens[:-1])
        return value


class AutoDbDeterministicBrandBindingService:
    def __init__(self):
        self.normalizer = DeterministicBrandNormalizer()

    def run(self, *, apply_changes: bool = True) -> dict[str, Any]:
        before = self._integrity_snapshot()
        suppliers = self._load_suppliers()
        supplier_by_id = {item.supplier_id: item for item in suppliers}
        variant_index = self._build_supplier_variant_index(suppliers)
        alias_map = self._load_alias_map()
        brand_stats = self._load_brand_stats()

        candidate_rows, candidate_meta = self._build_candidates(
            suppliers=suppliers,
            supplier_by_id=supplier_by_id,
            variant_index=variant_index,
            alias_map=alias_map,
            brand_stats=brand_stats,
        )

        requested_rows = self._requested_precheck(candidate_rows=candidate_rows, suppliers=suppliers)

        dry_rows, dry_summary, clean_rows = self._build_dry_run(candidate_rows, alias_map)

        apply_rows: list[dict[str, Any]] = []
        apply_summary = {
            "aliases_created": 0,
            "aliases_skipped_existing": 0,
            "product_rows_bound": 0,
            "display_rows_fixed": 0,
            "failed": 0,
            "blocked_conflicts": int(dry_summary["aliases_blocked_conflict"]),
            "blocked_ambiguous": int(dry_summary["ambiguous_blocked"]),
            "blocked_existing_different_supplier": int(dry_summary["existing_different_supplier_blocked"]),
            "manually_locked_skipped": int(dry_summary["manually_locked_skipped"]),
        }

        can_apply = (
            int(dry_summary["aliases_blocked_conflict"]) == 0
            and int(dry_summary["ambiguous_blocked"]) == 0
            and len(clean_rows) > 0
        )

        if apply_changes and can_apply:
            apply_rows, apply_summary = self._apply(clean_rows, alias_map)

        repeat_rows, repeat_summary, _ = self._build_dry_run(
            self._build_candidates(
                suppliers=suppliers,
                supplier_by_id=supplier_by_id,
                variant_index=variant_index,
                alias_map=self._load_alias_map(),
                brand_stats=self._load_brand_stats(),
            )[0],
            self._load_alias_map(),
        )

        verification_rows = self._verification_rows()

        coverage_rows, coverage_summary = self._brand_coverage_after()
        queue_rows, queue_summary = self._quality_queue_after()

        after = self._integrity_snapshot()
        integrity_rows, integrity_summary = self._integrity_report_rows(before=before, after=after)

        rollback_note = self._rollback_note(apply_rows)

        return {
            "candidate_rows": candidate_rows,
            "candidate_meta": candidate_meta,
            "requested_rows": requested_rows,
            "dry_rows": dry_rows,
            "dry_summary": dry_summary,
            "apply_rows": apply_rows,
            "apply_summary": apply_summary,
            "repeat_rows": repeat_rows,
            "repeat_summary": repeat_summary,
            "verification_rows": verification_rows,
            "coverage_rows": coverage_rows,
            "coverage_summary": coverage_summary,
            "queue_rows": queue_rows,
            "queue_summary": queue_summary,
            "integrity_rows": integrity_rows,
            "integrity_summary": integrity_summary,
            "rollback_note": rollback_note,
        }

    def write_exports(self, payload: dict[str, Any]) -> dict[str, Path]:
        out: dict[str, Path] = {}

        out["candidates_csv"], out["candidates_md"], _ = write_report(
            command_name="autodb_diacritics_brand_candidates",
            run_id=None,
            rows=payload["candidate_rows"],
            title="Auto_DB deterministic diacritics brand candidates",
            summary=payload["candidate_meta"],
            export_prefix="/tmp/autodb_diacritics_brand_candidates",
        )

        out["requested_csv"], out["requested_md"], _ = write_report(
            command_name="autodb_diacritics_requested_brands_precheck",
            run_id=None,
            rows=payload["requested_rows"],
            title="Auto_DB deterministic requested brands precheck",
            summary={"requested_count": len(REQUESTED_BRANDS)},
            export_prefix="/tmp/autodb_diacritics_requested_brands_precheck",
        )

        out["dry_csv"], out["dry_md"], _ = write_report(
            command_name="autodb_diacritics_brand_apply_dry_run",
            run_id=None,
            rows=payload["dry_rows"],
            title="Auto_DB deterministic brand apply dry-run",
            summary=payload["dry_summary"],
            export_prefix="/tmp/autodb_diacritics_brand_apply_dry_run",
        )

        out["apply_csv"], out["apply_md"], _ = write_report(
            command_name="autodb_diacritics_brand_apply_result",
            run_id=None,
            rows=payload["apply_rows"],
            title="Auto_DB deterministic brand apply result",
            summary=payload["apply_summary"],
            export_prefix="/tmp/autodb_diacritics_brand_apply_result",
        )

        out["repeat_csv"], out["repeat_md"], _ = write_report(
            command_name="autodb_diacritics_brand_repeat_dry",
            run_id=None,
            rows=payload["repeat_rows"],
            title="Auto_DB deterministic brand repeat dry-run",
            summary=payload["repeat_summary"],
            export_prefix="/tmp/autodb_diacritics_brand_repeat_dry",
        )

        out["verification_csv"], out["verification_md"], _ = write_report(
            command_name="autodb_diacritics_brand_verification",
            run_id=None,
            rows=payload["verification_rows"],
            title="Auto_DB deterministic brand verification",
            summary={"groups": len(payload["verification_rows"])},
            export_prefix="/tmp/autodb_diacritics_brand_verification",
        )

        out["coverage_csv"], out["coverage_md"], _ = write_report(
            command_name="autodb_brand_coverage_after_diacritics_binding",
            run_id=None,
            rows=payload["coverage_rows"],
            title="Auto_DB brand coverage after deterministic diacritics binding",
            summary=payload["coverage_summary"],
            export_prefix="/tmp/autodb_brand_coverage_after_diacritics_binding",
        )

        out["queue_csv"], out["queue_md"], _ = write_report(
            command_name="autodb_v3_quality_queue_after_diacritics_binding",
            run_id=None,
            rows=payload["queue_rows"],
            title="Auto_DB quality queue after deterministic diacritics binding",
            summary=payload["queue_summary"],
            export_prefix="/tmp/autodb_v3_quality_queue_after_diacritics_binding",
        )

        out["integrity_csv"], out["integrity_md"], _ = write_report(
            command_name="autodb_diacritics_brand_integrity",
            run_id=None,
            rows=payload["integrity_rows"],
            title="Auto_DB deterministic brand integrity",
            summary=payload["integrity_summary"],
            export_prefix="/tmp/autodb_diacritics_brand_integrity",
        )

        rollback_path = Path("/tmp/autodb_diacritics_brand_rollback_note.md")
        rollback_path.write_text(payload["rollback_note"], encoding="utf-8")
        out["rollback_md"] = rollback_path

        final_path = Path("/tmp/autodb_diacritics_brand_binding_final_report.md")
        final_lines = [
            "# Auto_DB deterministic diacritics brand binding final report",
            "",
            f"- detected_candidates: {payload['candidate_meta'].get('detected_candidates', 0)}",
            f"- clean_apply_candidates: {payload['dry_summary'].get('candidate_count', 0)}",
            f"- aliases_created: {payload['apply_summary'].get('aliases_created', 0)}",
            f"- product_rows_bound: {payload['apply_summary'].get('product_rows_bound', 0)}",
            f"- display_rows_fixed: {payload['apply_summary'].get('display_rows_fixed', 0)}",
            f"- brand_coverage_rows: {payload['coverage_summary'].get('rows', 0)}",
            f"- quality_queue_size: {payload['queue_summary'].get('queue_size', 0)}",
            "- no_product_links: true",
            "- no_enrichment: true",
            "- no_images: true",
            "- no_import: true",
            "- no_utr_api: true",
            "- no_price_stock_productprice_changes: true",
            "",
            "## Requested brands",
        ]
        important = {
            "LEMFORDER",
            "LESJOFORS",
            "LOBRO",
            "NURAL",
            "DURER",
            "EBERSPACHER",
            "KALE OTO RADYATOR",
            "MALO",
            "NEOLUX",
            "SCHLUTTER TURBOLADER",
            "SPAHN GLUHLAMPEN",
        }
        for row in payload["requested_rows"]:
            if str(row.get("requested_brand") or "") not in important:
                continue
            final_lines.append(
                f"- {row.get('requested_brand')}: decision={row.get('decision')} supplier_id={row.get('supplier_id') or '-'} apply={row.get('will_apply')} reason={row.get('reason')}"
            )

        final_path.write_text("\n".join(final_lines) + "\n", encoding="utf-8")
        out["final_md"] = final_path
        return out

    def _load_suppliers(self) -> list[SupplierEntry]:
        with connections["auto_db_pro"].cursor() as cursor:
            cursor.execute(
                """
                SELECT id, description, matchcode, COALESCE(nbrofarticles, 0)
                FROM suppliers
                """
            )
            rows = cursor.fetchall()
        out: list[SupplierEntry] = []
        for row in rows:
            try:
                supplier_id = int(row[0])
            except (TypeError, ValueError):
                continue
            description = str(row[1] or "").strip()
            matchcode = str(row[2] or "").strip()
            if not description:
                continue
            nbrofarticles = int(row[3] or 0)
            variants = set(self.normalizer.variants(description))
            variants.update(self.normalizer.variants(matchcode))
            variants.update(self.normalizer.variants(normalize_brand(description)))
            variants.update(self.normalizer.variants(normalize_brand(matchcode)))
            if not variants:
                continue
            out.append(
                SupplierEntry(
                    supplier_id=supplier_id,
                    description=description,
                    matchcode=matchcode,
                    nbrofarticles=max(nbrofarticles, 0),
                    variants=tuple(sorted(variants)),
                )
            )
        out.sort(key=lambda item: (-item.nbrofarticles, item.supplier_id))
        return out

    def _build_supplier_variant_index(self, suppliers: list[SupplierEntry]) -> dict[str, set[int]]:
        out: dict[str, set[int]] = defaultdict(set)
        for supplier in suppliers:
            for variant in supplier.variants:
                out[variant].add(supplier.supplier_id)
        return out

    def _load_alias_map(self) -> dict[str, AutoDbSupplierBrandAlias]:
        out: dict[str, AutoDbSupplierBrandAlias] = {}
        queryset = AutoDbSupplierBrandAlias.objects.filter(is_active=True).order_by("-manual_confirmed", "-confidence", "created_at")
        for item in queryset:
            key = normalize_brand(item.normalized_raw_brand or item.raw_brand)
            if key and key not in out:
                out[key] = item
        return out

    def _load_brand_stats(self) -> dict[int, dict[str, Any]]:
        try:
            brand_rows = (
                Brand.objects.annotate(
                    product_count=Count("products"),
                    products_missing_autodb_supplier_id=Count("products", filter=Q(products__autodb_supplier_id__isnull=True)),
                    manually_locked_count=Count("products", filter=Q(products__brand_manually_locked=True)),
                )
                .filter(product_count__gt=0)
                .values("id", "name", "product_count", "products_missing_autodb_supplier_id", "manually_locked_count")
            )
        except (OperationalError, ProgrammingError):
            return {}

        supplier_rows = (
            Product.objects.filter(brand_id__in=[item["id"] for item in brand_rows], autodb_supplier_id__isnull=False)
            .values("brand_id", "autodb_supplier_id")
            .annotate(cnt=Count("id"))
        )
        supplier_counts: dict[str, dict[int, int]] = defaultdict(dict)
        for row in supplier_rows:
            supplier_counts[str(row["brand_id"])][int(row["autodb_supplier_id"])] = int(row["cnt"])

        sample_skus = self._sample_skus_map([str(item["id"]) for item in brand_rows])

        out: dict[str, dict[str, Any]] = {}
        for row in brand_rows:
            brand_id = str(row["id"])
            out[brand_id] = {
                "brand_id": brand_id,
                "brand_name": str(row["name"] or "").strip(),
                "product_count": int(row["product_count"] or 0),
                "missing_count": int(row["products_missing_autodb_supplier_id"] or 0),
                "manually_locked_count": int(row["manually_locked_count"] or 0),
                "supplier_counts": supplier_counts.get(brand_id, {}),
                "sample_skus": sample_skus.get(brand_id, []),
            }
        return out

    def _sample_skus_map(self, brand_ids: list[str]) -> dict[str, list[str]]:
        if not brand_ids:
            return {}
        out: dict[str, list[str]] = defaultdict(list)
        queryset = (
            Product.objects.filter(brand_id__in=brand_ids)
            .order_by("brand_id", "sku")
            .values("brand_id", "sku", "svom_sku")
        )
        for row in queryset.iterator(chunk_size=10000):
            brand_id = str(row["brand_id"])
            if len(out[brand_id]) >= 5:
                continue
            sku = str(row.get("svom_sku") or row.get("sku") or "").strip()
            if sku:
                out[brand_id].append(sku)
        return out

    def _build_candidates(
        self,
        *,
        suppliers: list[SupplierEntry],
        supplier_by_id: dict[int, SupplierEntry],
        variant_index: dict[str, set[int]],
        alias_map: dict[str, AutoDbSupplierBrandAlias],
        brand_stats: dict[str, dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        decision_counter: Counter[str] = Counter()

        for stats in brand_stats.values():
            brand_id = str(stats["brand_id"])
            brand_name = str(stats["brand_name"])
            normalized = normalize_brand(brand_name)
            variants = self.normalizer.variants(brand_name)
            alias = alias_map.get(normalized)

            supplier_ids = set()
            match_variant = ""
            for variant in sorted(variants):
                hits = variant_index.get(variant) or set()
                if hits:
                    supplier_ids.update(hits)
                    if not match_variant:
                        match_variant = variant

            if supplier_ids:
                active_ids = {item for item in supplier_ids if int(supplier_by_id[item].nbrofarticles or 0) > 0}
                if active_ids:
                    supplier_ids = active_ids

            supplier: SupplierEntry | None = None
            decision = "missing_local_supplier"
            reason = "no deterministic supplier variant match in auto_db_pro.suppliers"
            match_reason = ""

            if normalized in {normalize_brand(item) for item in NON_TECDOC_BRAND_KEYS}:
                decision = "skipped_non_tecdoc"
                reason = "brand in non-TecDoc blocked list"
            elif normalized in {normalize_brand(item) for item in UNSAFE_BRAND_KEYS}:
                decision = "skipped_split_or_unsafe"
                reason = "brand in unsafe/split blocked list"
            elif alias is not None:
                supplier = supplier_by_id.get(int(alias.autodb_supplier_id))
                if supplier is not None:
                    decision = "clean_apply_candidate"
                    reason = "resolved via existing approved Auto_DB alias"
                    match_reason = "existing_alias"
                else:
                    decision = "missing_local_supplier"
                    reason = "alias supplier missing in auto_db_pro.suppliers"
            elif len(supplier_ids) == 1:
                supplier = supplier_by_id.get(int(next(iter(supplier_ids))))
                if supplier is not None:
                    decision = "clean_apply_candidate"
                    reason = "deterministic diacritics/trademark variant match"
                    match_reason = f"variant:{match_variant}" if match_variant else "variant"
            elif len(supplier_ids) > 1:
                decision = "unsafe_ambiguous"
                reason = "multiple supplier candidates after deterministic variant matching"

            product_count = int(stats["product_count"])
            missing_count = int(stats["missing_count"])
            locked_count = int(stats["manually_locked_count"])
            supplier_counts: dict[int, int] = dict(stats["supplier_counts"])

            same_count = 0
            different_count = 0
            if supplier is not None:
                same_count = int(supplier_counts.get(int(supplier.supplier_id), 0))
                different_count = int(sum(supplier_counts.values()) - same_count)
                if different_count > 0:
                    decision = "blocked_existing_different_supplier"
                    reason = "existing Product.autodb_supplier_id points to different supplier"
                elif locked_count >= product_count:
                    decision = "skipped_manual_locked_only"
                    reason = "all products for brand are manually locked"
                elif same_count >= product_count and missing_count == 0:
                    decision = "skip_existing_same"
                    reason = "all products already bound to same supplier"

            supplier_id_text = str(supplier.supplier_id) if supplier is not None else ""
            supplier_desc = supplier.description if supplier is not None else ""
            supplier_matchcode = supplier.matchcode if supplier is not None else ""
            supplier_variants = ";".join(list(supplier.variants)[:40]) if supplier is not None else ""
            confidence = "1.00" if decision in {"clean_apply_candidate", "skip_existing_same"} else "0.00"

            row = asdict(
                BrandCandidate(
                    catalog_brand_id=str(brand_id),
                    catalog_brand_name=brand_name,
                    normalized_catalog_brand=normalized,
                    generated_catalog_variants=";".join(sorted(variants)[:40]),
                    autodb_supplier_id=supplier_id_text,
                    autodb_supplier_description=supplier_desc,
                    autodb_supplier_matchcode=supplier_matchcode,
                    generated_supplier_variants=supplier_variants,
                    match_reason=match_reason,
                    product_count=product_count,
                    products_missing_autodb_supplier_id=missing_count,
                    products_existing_same_supplier=same_count,
                    products_existing_different_supplier=different_count,
                    manually_locked_count=locked_count,
                    decision=decision,
                    confidence=confidence,
                    reason=reason,
                    sample_skus=",".join(stats["sample_skus"]),
                )
            )
            rows.append(row)
            decision_counter[decision] += 1

        meta = {
            "detected_candidates": len(rows),
            "decision_distribution": dict(decision_counter),
        }
        return rows, meta

    def _requested_precheck(self, *, candidate_rows: list[dict[str, Any]], suppliers: list[SupplierEntry]) -> list[dict[str, Any]]:
        by_norm: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in candidate_rows:
            by_norm[normalize_brand(str(row.get("catalog_brand_name") or ""))].append(row)
        supplier_name_map: dict[str, list[SupplierEntry]] = defaultdict(list)
        for supplier in suppliers:
            supplier_name_map[normalize_brand(supplier.description)].append(supplier)
            supplier_name_map[normalize_brand(supplier.matchcode)].append(supplier)

        rows: list[dict[str, Any]] = []
        for requested in REQUESTED_BRANDS:
            normalized = normalize_brand(requested)
            hits = by_norm.get(normalized, [])
            suppliers_hit = supplier_name_map.get(normalized, [])
            if not hits:
                rows.append(
                    {
                        "requested_brand": requested,
                        "raw_catalog_brand": "",
                        "local_autodb_supplier_candidate": "; ".join(
                            f"{item.supplier_id}:{item.description}" for item in suppliers_hit[:5]
                        ),
                        "supplier_id": "",
                        "generated_variants": ";".join(sorted(self.normalizer.variants(requested))[:20]),
                        "product_count": 0,
                        "reason": "brand not found in catalog brands with products",
                        "safe_to_apply": "no",
                        "will_apply": "no",
                        "decision": "missing_catalog_brand",
                    }
                )
                continue
            for hit in hits:
                decision = str(hit.get("decision") or "")
                rows.append(
                    {
                        "requested_brand": requested,
                        "raw_catalog_brand": hit.get("catalog_brand_name") or "",
                        "local_autodb_supplier_candidate": f"{hit.get('autodb_supplier_id') or ''}:{hit.get('autodb_supplier_description') or ''}".strip(":"),
                        "supplier_id": hit.get("autodb_supplier_id") or "",
                        "generated_variants": hit.get("generated_catalog_variants") or "",
                        "product_count": int(hit.get("product_count") or 0),
                        "reason": hit.get("reason") or "",
                        "safe_to_apply": "yes" if decision == "clean_apply_candidate" else "no",
                        "will_apply": "yes" if decision == "clean_apply_candidate" else "no",
                        "decision": decision,
                    }
                )
        return rows

    def _build_dry_run(
        self,
        candidate_rows: list[dict[str, Any]],
        alias_map: dict[str, AutoDbSupplierBrandAlias],
    ) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
        rows: list[dict[str, Any]] = []
        summary = Counter()
        clean: list[dict[str, Any]] = []

        for row in candidate_rows:
            decision = str(row.get("decision") or "")
            if decision != "clean_apply_candidate":
                if decision == "unsafe_ambiguous":
                    summary["ambiguous_blocked"] += 1
                if decision == "blocked_existing_different_supplier":
                    summary["existing_different_supplier_blocked"] += int(row.get("products_existing_different_supplier") or 0)
                if decision == "skipped_manual_locked_only":
                    summary["manually_locked_skipped"] += int(row.get("manually_locked_count") or 0)
                continue

            normalized = normalize_brand(str(row.get("catalog_brand_name") or ""))
            supplier_id = int(row.get("autodb_supplier_id") or 0)
            alias = alias_map.get(normalized)
            alias_action = "would_create"
            alias_reason = "create deterministic alias"
            if alias is not None and int(alias.autodb_supplier_id) == supplier_id:
                alias_action = "skip_existing_same"
                alias_reason = "alias already exists with same supplier"
                summary["aliases_skip_existing_same"] += 1
            elif alias is not None and int(alias.autodb_supplier_id) != supplier_id:
                alias_action = "blocked_conflict"
                alias_reason = "existing alias points to different supplier"
                summary["aliases_blocked_conflict"] += 1
            else:
                summary["aliases_would_create"] += 1

            bind_count = self._count_bind_rows(brand_id=str(row["catalog_brand_id"]))
            display_fix = self._count_display_fix_rows(
                brand_id=str(row["catalog_brand_id"]),
                supplier_id=supplier_id,
                supplier_name=str(row.get("autodb_supplier_description") or ""),
            )

            if alias_action == "blocked_conflict":
                continue

            summary["candidate_count"] += 1
            summary["products_would_bind"] += bind_count
            summary["products_display_would_fix"] += display_fix
            dry = {
                **row,
                "alias_action": alias_action,
                "alias_reason": alias_reason,
                "products_would_bind": bind_count,
                "products_display_would_fix": display_fix,
            }
            rows.append(dry)
            clean.append(dry)

        summary.setdefault("candidate_count", 0)
        summary.setdefault("aliases_would_create", 0)
        summary.setdefault("aliases_skip_existing_same", 0)
        summary.setdefault("aliases_blocked_conflict", 0)
        summary.setdefault("products_would_bind", 0)
        summary.setdefault("products_display_would_fix", 0)
        summary.setdefault("manually_locked_skipped", 0)
        summary.setdefault("existing_different_supplier_blocked", 0)
        summary.setdefault("ambiguous_blocked", 0)

        return rows, dict(summary), clean

    def _apply(self, rows: list[dict[str, Any]], alias_map: dict[str, AutoDbSupplierBrandAlias]) -> tuple[list[dict[str, Any]], dict[str, int]]:
        out: list[dict[str, Any]] = []
        summary = Counter()
        now = timezone.now()
        with transaction.atomic():
            for row in rows:
                brand_id = str(row["catalog_brand_id"])
                brand_name = str(row.get("catalog_brand_name") or "")
                supplier_id = int(row.get("autodb_supplier_id") or 0)
                supplier_name = str(row.get("autodb_supplier_description") or "")
                normalized = normalize_brand(brand_name)
                expected_hash = hashlib.sha1(f"{supplier_id}:{Product.BRAND_SOURCE_AUTODB_PRO}:{supplier_name}".encode("utf-8")).hexdigest()

                alias = alias_map.get(normalized)
                alias_action = "skipped_existing"
                if alias is None:
                    alias = AutoDbSupplierBrandAlias.objects.create(
                        raw_brand=brand_name,
                        autodb_supplier_id=supplier_id,
                        autodb_supplier_name=supplier_name,
                        source=AutoDbSupplierBrandAlias.SOURCE_MANUAL,
                        confidence=Decimal("100.00"),
                        manual_confirmed=True,
                        note="deterministic_diacritics_binding",
                        is_active=True,
                    )
                    alias_map[normalized] = alias
                    alias_action = "created"
                    summary["aliases_created"] += 1
                else:
                    summary["aliases_skipped_existing"] += 1

                bind_qs = Product.objects.filter(
                    brand_id=brand_id,
                    brand_manually_locked=False,
                    autodb_supplier_id__isnull=True,
                )
                bound = bind_qs.update(
                    autodb_supplier_id=supplier_id,
                    autodb_supplier_name=supplier_name,
                    display_brand_name=supplier_name,
                    brand_source=Product.BRAND_SOURCE_AUTODB_PRO,
                    brand_source_hash=expected_hash,
                    updated_at=now,
                )
                summary["product_rows_bound"] += int(bound)

                fix_qs = Product.objects.filter(
                    brand_id=brand_id,
                    brand_manually_locked=False,
                    autodb_supplier_id=supplier_id,
                ).filter(
                    Q(autodb_supplier_name="")
                    | ~Q(autodb_supplier_name=supplier_name)
                    | Q(display_brand_name="")
                    | ~Q(display_brand_name=supplier_name)
                    | ~Q(brand_source=Product.BRAND_SOURCE_AUTODB_PRO)
                    | Q(brand_source_hash="")
                    | ~Q(brand_source_hash=expected_hash)
                )
                fixed = fix_qs.update(
                    autodb_supplier_name=supplier_name,
                    display_brand_name=supplier_name,
                    brand_source=Product.BRAND_SOURCE_AUTODB_PRO,
                    brand_source_hash=expected_hash,
                    updated_at=now,
                )
                summary["display_rows_fixed"] += int(fixed)

                out.append(
                    {
                        "catalog_brand_id": brand_id,
                        "catalog_brand_name": brand_name,
                        "autodb_supplier_id": supplier_id,
                        "autodb_supplier_name": supplier_name,
                        "alias_action": alias_action,
                        "product_rows_bound": int(bound),
                        "display_rows_fixed": int(fixed),
                        "failed": 0,
                    }
                )

        summary.setdefault("aliases_created", 0)
        summary.setdefault("aliases_skipped_existing", 0)
        summary.setdefault("product_rows_bound", 0)
        summary.setdefault("display_rows_fixed", 0)
        summary.setdefault("failed", 0)
        summary.setdefault("blocked_conflicts", 0)
        summary.setdefault("blocked_ambiguous", 0)
        summary.setdefault("blocked_existing_different_supplier", 0)
        summary.setdefault("manually_locked_skipped", 0)
        return out, dict(summary)

    def _count_bind_rows(self, *, brand_id: str) -> int:
        return Product.objects.filter(brand_id=brand_id, autodb_supplier_id__isnull=True, brand_manually_locked=False).count()

    def _count_display_fix_rows(self, *, brand_id: str, supplier_id: int, supplier_name: str) -> int:
        expected_hash = hashlib.sha1(f"{supplier_id}:{Product.BRAND_SOURCE_AUTODB_PRO}:{supplier_name}".encode("utf-8")).hexdigest()
        return (
            Product.objects.filter(brand_id=brand_id, brand_manually_locked=False, autodb_supplier_id=supplier_id)
            .filter(
                Q(autodb_supplier_name="")
                | ~Q(autodb_supplier_name=supplier_name)
                | Q(display_brand_name="")
                | ~Q(display_brand_name=supplier_name)
                | ~Q(brand_source=Product.BRAND_SOURCE_AUTODB_PRO)
                | Q(brand_source_hash="")
                | ~Q(brand_source_hash=expected_hash)
            )
            .count()
        )

    def _verification_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        groups = [
            ("LEMFORDER / LEMFÖRDER", ["LEMFORDER", "LEMFÖRDER", "LEMFOERDER"]),
            ("LESJOFORS / LESJÖFORS", ["LESJOFORS", "LESJÖFORS", "LESJOEFORS"]),
            ("LOBRO / LÖBRO", ["LOBRO", "LÖBRO", "LOEBRO"]),
            ("NURAL / NÜRAL", ["NURAL", "NÜRAL", "NUERAL"]),
            ("DURER / DÜRER", ["DURER", "DÜRER"]),
            ("EBERSPACHER / EBERSPÄCHER", ["EBERSPACHER", "EBERSPAECHER", "EBERSPÄCHER"]),
            ("KALE OTO RADYATOR / KALE OTO RADYATÖR", ["KALE OTO RADYATOR", "KALE OTO RADYATÖR"]),
            ("MALO", ["MALO", "MALÒ", "MALÓ", "MALÖ"]),
            ("NEOLUX / NEOLUX®", ["NEOLUX", "NEOLUX R", "NEOLUX ®", "NEOLUX®"]),
            ("SCHLUTTER TURBOLADER / SCHLÜTTER TURBOLADER", ["SCHLUTTER TURBOLADER", "SCHLUETTER TURBOLADER", "SCHLÜTTER TURBOLADER"]),
            ("SPAHN GLUHLAMPEN / SPAHN GLÜHLAMPEN", ["SPAHN GLUHLAMPEN", "SPAHN GLUEHLAMPEN", "SPAHN GLÜHLAMPEN"]),
        ]

        aliases = {
            normalize_brand(item.normalized_raw_brand or item.raw_brand): item
            for item in AutoDbSupplierBrandAlias.objects.filter(is_active=True)
        }

        for label, names in groups:
            normalized_set = {normalize_brand(item) for item in names}
            try:
                brand_ids = list(
                    Brand.objects.filter(name__in=names).values_list("id", flat=True)
                )
            except (OperationalError, ProgrammingError):
                brand_ids = []
            products = Product.objects.filter(brand_id__in=brand_ids)
            product_count = products.count()
            supplier_counts = Counter(int(item or 0) for item in products.values_list("autodb_supplier_id", flat=True))
            top_supplier_id = max(supplier_counts, key=supplier_counts.get) if supplier_counts else 0
            expected_supplier_name = ""
            if top_supplier_id > 0:
                with connections["auto_db_pro"].cursor() as cursor:
                    cursor.execute("SELECT description FROM suppliers WHERE id=%s LIMIT 1", [top_supplier_id])
                    row = cursor.fetchone()
                    expected_supplier_name = str((row[0] if row else "") or "")
            alias_exists = any(key in aliases for key in normalized_set)
            locked = products.filter(brand_manually_locked=True).count()
            different_blocked = products.filter(autodb_supplier_id__isnull=False).exclude(autodb_supplier_id=top_supplier_id or None).count() if top_supplier_id else 0
            sample_skus = list(products.order_by("sku").values_list("svom_sku", "sku")[:5])
            rows.append(
                {
                    "group": label,
                    "catalog_brand_product_count": product_count,
                    "products_with_expected_autodb_supplier_id": int(supplier_counts.get(top_supplier_id, 0)) if top_supplier_id else 0,
                    "expected_supplier_id": top_supplier_id or "",
                    "expected_supplier_name": expected_supplier_name,
                    "display_brand_name": expected_supplier_name,
                    "brand_source": Product.BRAND_SOURCE_AUTODB_PRO if top_supplier_id else "",
                    "alias_exists": "yes" if alias_exists else "no",
                    "conflict_count": int(different_blocked),
                    "manually_locked_skipped_count": int(locked),
                    "existing_different_supplier_blocked_count": int(different_blocked),
                    "sample_skus": ",".join(str(a or b or "") for a, b in sample_skus),
                }
            )
        return rows

    def _brand_coverage_after(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        rows_obj = AutoDbBrandCoverageAuditService().audit(supplier_code="", limit=0)
        rows = [asdict(item) for item in rows_obj]
        decision = Counter(str(item.get("decision") or "") for item in rows)
        summary = {
            "rows": len(rows),
            "total_brand_groups": len(rows),
            "mapped": int(decision.get("mapped", 0)),
            "keep_unmapped_missing_supplier": int(decision.get("keep_unmapped_missing_supplier", 0)),
            "needs_alias": int(decision.get("needs_alias", 0)),
            "unsafe_ambiguous": int(decision.get("unsafe_ambiguous", 0)),
            "split_brand_needed": int(decision.get("split_brand_needed", 0)),
            "non_tecdoc": int(decision.get("non_tecdoc", 0)),
            "needs_human_approval": int(decision.get("needs_human_approval", 0)),
        }
        return rows, summary

    def _quality_queue_after(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        limit = SupplierOffer.objects.count()
        rows_obj = AutoDbMatchJobBuilder().build_jobs(run=None, supplier_code="", limit=limit, dry_run=True)
        rows = [asdict(item) for item in rows_obj]

        by_supplier = Counter(str(item.get("supplier_code") or "-") for item in rows)
        by_brand = Counter(str(item.get("normalized_brand") or "-") for item in rows)
        by_resolver = Counter(str(item.get("resolver_source") or "unresolved") for item in rows)
        by_article = Counter(str(item.get("article_source_type") or "-") for item in rows)
        by_status = Counter(str(item.get("status") or "-") for item in rows)
        paused_statuses = {
            "skipped_non_tecdoc",
            "skipped_brand_unresolved",
            "skipped_split_needed",
            "skipped_unsafe_ambiguous",
            "skipped_bad_article_source",
            "quota_paused",
        }
        paused = {key: value for key, value in by_status.items() if key in paused_statuses}

        summary = {
            "queue_size": len(rows),
            "rows_by_supplier_code": dict(by_supplier),
            "rows_by_brand_top_50": dict(by_brand.most_common(50)),
            "rows_by_resolver_source": dict(by_resolver),
            "rows_by_article_source": dict(by_article),
            "excluded_counts_by_status": dict(by_status),
            "paused_buckets": paused,
        }
        return rows, summary

    def _integrity_snapshot(self) -> dict[str, Any]:
        return {
            "product_count": Product.objects.count(),
            "supplieroffer_count": SupplierOffer.objects.count(),
            "productprice_count": ProductPrice.objects.count(),
            "productattribute_count": ProductAttribute.objects.count(),
            "productfitment_count": ProductFitment.objects.count(),
            "productimage_count": ProductImage.objects.count(),
            "linked_by_key_count": Product.objects.exclude(autodb_article_key="").count(),
            "quality_trusted_count": AutoDbProductLinkQuality.objects.filter(status=AutoDbProductLinkQuality.STATUS_TRUSTED).count(),
            "quality_suspicious_count": AutoDbProductLinkQuality.objects.filter(status=AutoDbProductLinkQuality.STATUS_SUSPICIOUS).count(),
            "autodb_supplier_brand_alias_count": AutoDbSupplierBrandAlias.objects.count(),
            "product_autodb_supplier_nonnull_count": Product.objects.filter(autodb_supplier_id__isnull=False).count(),
            "display_brand_name_nonempty_count": Product.objects.exclude(display_brand_name="").count(),
            "brand_source_autodb_pro_count": Product.objects.filter(brand_source=Product.BRAND_SOURCE_AUTODB_PRO).count(),
            "sum_supplier_stock_qty": SupplierOffer.objects.aggregate(v=Sum("stock_qty"))["v"] or 0,
            "sum_supplier_purchase_price": SupplierOffer.objects.aggregate(v=Sum("purchase_price"))["v"] or 0,
            "sum_productprice_final_price": ProductPrice.objects.aggregate(v=Sum("final_price"))["v"] or 0,
            "utr_api_calls": 0,
        }

    def _integrity_report_rows(self, *, before: dict[str, Any], after: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        keys = sorted(set(before) | set(after))
        rows: list[dict[str, Any]] = []
        for key in keys:
            rows.append(
                {
                    "metric": key,
                    "before": before.get(key),
                    "after": after.get(key),
                    "delta": self._delta(before.get(key), after.get(key)),
                    "changed": before.get(key) != after.get(key),
                }
            )
        summary = {
            "allowed_deltas": [
                "autodb_supplier_brand_alias_count",
                "product_autodb_supplier_nonnull_count",
                "display_brand_name_nonempty_count",
                "brand_source_autodb_pro_count",
            ],
            "utr_api_calls": 0,
            "no_product_links": True,
            "no_enrichment": True,
            "no_images": True,
            "no_import": True,
        }
        return rows, summary

    def _delta(self, before: Any, after: Any) -> str:
        try:
            return str((after or 0) - (before or 0))
        except Exception:  # noqa: BLE001
            return ""

    def _rollback_note(self, apply_rows: list[dict[str, Any]]) -> str:
        now = timezone.now().isoformat()
        supplier_ids = sorted({int(item.get("autodb_supplier_id") or 0) for item in apply_rows if int(item.get("autodb_supplier_id") or 0) > 0})
        brand_ids = sorted({str(item.get("catalog_brand_id") or "").strip() for item in apply_rows if str(item.get("catalog_brand_id") or "").strip()})
        lines = [
            "# Auto_DB deterministic diacritics brand binding rollback note",
            "",
            f"- generated_at: {now}",
            f"- affected_brand_ids: {brand_ids}",
            f"- affected_supplier_ids: {supplier_ids}",
            "- fields_changed_on_product: autodb_supplier_id, autodb_supplier_name, display_brand_name, brand_source, brand_source_hash, updated_at",
            "- aliases_created_table: autodb_supplier_brand_aliases",
            "- rollback_scope: brand-level only; no Product article link fields touched",
            "",
            "Rollback approach:",
            "1. Identify product rows by brand_id in affected_brand_ids and updated_at window around this run.",
            "2. For rows updated from NULL autodb_supplier_id to new supplier_id, set autodb_supplier_id back to NULL and clear brand display fields if they were empty before.",
            "3. For display-only fixes on existing same supplier rows, restore previous display fields from pre-run backup if required.",
            "4. Delete aliases created by this run with note=deterministic_diacritics_binding and raw_brand in affected brands.",
            "5. Product links/enrichment/images/price-stock are unaffected because this run never writes autodb_article_number/autodb_article_key/ProductPrice/ProductImage/ProductAttribute/ProductFitment.",
            "",
        ]
        return "\n".join(lines)
