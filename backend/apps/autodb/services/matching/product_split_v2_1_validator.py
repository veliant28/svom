from __future__ import annotations

import ast
import csv
from collections import Counter
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from apps.catalog.models import Brand, Product
from apps.pricing.models import ProductPrice, SupplierOffer
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_brand

from .reports import write_report


def _canonical_article(value: str) -> str:
    return "".join(ch for ch in str(value or "").upper() if ch.isalnum())


def _as_tuple_ids(raw: str) -> tuple[str, ...]:
    text = str(raw or "").strip()
    if not text:
        return tuple()
    try:
        parsed = ast.literal_eval(text)
    except Exception:
        parsed = None
    if isinstance(parsed, (list, tuple, set)):
        return tuple(sorted({str(item).strip() for item in parsed if str(item).strip()}))
    if "," in text:
        return tuple(sorted({part.strip() for part in text.split(",") if part.strip()}))
    return (text,)


def _load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


@dataclass(frozen=True)
class SplitV21Candidate:
    case_label: str
    sku: str
    source_product_id: str
    keep_group: str
    move_group: str
    keep_brand_norm: str
    move_brand_norm: str
    source_brand_after: str
    source_display_brand_after: str
    new_brand_after: str
    new_display_brand_after: str
    offers_to_move: tuple[str, ...]
    raw_offers_to_move: tuple[str, ...]
    source_productprice_ids: tuple[str, ...]


@dataclass(frozen=True)
class SplitV21ValidationResult:
    case_label: str
    sku: str
    source_product_id: str
    status: str
    clean: bool
    blockers: tuple[str, ...]
    source_catalog_brand: str
    source_display_brand: str
    expected_source_brand: str
    expected_new_brand: str
    keep_offer_count: int
    moved_offer_count: int
    source_productprice_purchase: str
    expected_source_purchase_from_keep: str
    expected_new_purchase_from_move: str
    source_catalog_brand_norm: str
    expected_source_brand_norm: str
    notes: str


class AutoDbProductSplitV21Validator:
    KNOWN_CASE_1 = Path("/tmp/product_quality_0S3V5O5M9202_split_v2_final_dry_run.csv")
    KNOWN_CASE_2 = Path("/tmp/product_quality_split_v2_one_final_dry_run.csv")
    REMAINING_CANDIDATES = Path("/tmp/product_quality_split_v2_batch_candidates.csv")

    OUT_KNOWN_CSV = "/tmp/product_quality_split_v2_1_validator_known_cases.csv"
    OUT_KNOWN_MD = "/tmp/product_quality_split_v2_1_validator_known_cases.md"
    OUT_REMAINING_CSV = "/tmp/product_quality_split_v2_1_remaining_candidates_validation.csv"
    OUT_REMAINING_MD = "/tmp/product_quality_split_v2_1_remaining_candidates_validation.md"
    OUT_FINAL_MD = "/tmp/product_quality_split_v2_1_validator_final_report.md"

    STATUS_CLEAN = "clean_pass"
    STATUS_BLOCKED = "blocked"
    STATUS_ALREADY_APPLIED = "already_applied_successfully"

    def run(self) -> dict[str, Any]:
        known_candidates = self._known_case_candidates()
        known_rows = [asdict(self.validate_candidate(candidate)) for candidate in known_candidates]

        known_summary = {
            "known_cases_checked": len(known_rows),
            "clean_or_already_applied": sum(
                1
                for row in known_rows
                if str(row.get("status")) in {self.STATUS_CLEAN, self.STATUS_ALREADY_APPLIED}
            ),
            "blocked": sum(1 for row in known_rows if str(row.get("status")) == self.STATUS_BLOCKED),
        }
        write_report(
            command_name="product_quality_split_v2_1_validator_known_cases",
            run_id="known",
            rows=known_rows,
            title="Split v2.1 validator known cases",
            summary=known_summary,
            export_prefix=self.OUT_KNOWN_CSV.replace(".csv", ""),
        )

        remaining_candidates = self._remaining_candidates()
        remaining_results = [self.validate_candidate(candidate) for candidate in remaining_candidates]
        remaining_rows = [asdict(item) for item in remaining_results]
        blocker_counter = Counter()
        for row in remaining_rows:
            for item in _as_tuple_ids(str(row.get("blockers") or "")):
                blocker_counter[item] += 1

        remaining_summary = {
            "total_checked": len(remaining_rows),
            "clean": sum(1 for row in remaining_rows if str(row.get("status")) == self.STATUS_CLEAN),
            "blocked": sum(1 for row in remaining_rows if str(row.get("status")) == self.STATUS_BLOCKED),
            "already_applied_successfully": sum(
                1 for row in remaining_rows if str(row.get("status")) == self.STATUS_ALREADY_APPLIED
            ),
            "top_blockers": tuple(blocker_counter.most_common(12)),
            "negative_cases_similar_to_4S5V3O6M6442": sum(
                1
                for row in remaining_rows
                if "source_productprice_basis_mismatch" in set(_as_tuple_ids(str(row.get("blockers") or "")))
                or "source_catalog_brand_mismatch_requires_update" in set(_as_tuple_ids(str(row.get("blockers") or "")))
            ),
        }
        write_report(
            command_name="product_quality_split_v2_1_remaining_candidates_validation",
            run_id="remaining",
            rows=remaining_rows,
            title="Split v2.1 validator remaining candidates",
            summary=remaining_summary,
            export_prefix=self.OUT_REMAINING_CSV.replace(".csv", ""),
        )

        clean_future_candidates = [
            row
            for row in remaining_rows
            if str(row.get("status")) == self.STATUS_CLEAN
        ]
        final_lines = [
            "# Split v2.1 validator final report",
            "",
            "1. validator rules:",
            "- brand consistency checks on source/new expected state and deterministic brand resolution",
            "- ProductPrice basis checks (source keep-offer basis, new moved-offer basis)",
            "- SupplierOffer + SupplierRawOffer move consistency checks",
            "- post-apply invariant simulation checks before apply",
            "",
            "2. known case results:",
            f"- total: {known_summary['known_cases_checked']}",
            f"- clean/already_applied: {known_summary['clean_or_already_applied']}",
            f"- blocked: {known_summary['blocked']}",
            "",
            "3. remaining candidate counts:",
            f"- total checked: {remaining_summary['total_checked']}",
            f"- clean: {remaining_summary['clean']}",
            f"- blocked: {remaining_summary['blocked']}",
            f"- already_applied_successfully: {remaining_summary['already_applied_successfully']}",
            "",
            "4. blockers:",
            f"- top blockers: {remaining_summary['top_blockers']}",
            f"- 4S5-like negative cases: {remaining_summary['negative_cases_similar_to_4S5V3O6M6442']}",
            "",
            "5. clean future apply candidates:",
            f"- clean rows count: {len(clean_future_candidates)}",
            "",
            "6. confirmation no writes:",
            "- validator uses read-only ORM queries; no Product/SupplierOffer/SupplierRawOffer/ProductPrice writes",
        ]
        Path(self.OUT_FINAL_MD).write_text("\n".join(final_lines) + "\n", encoding="utf-8")

        return {
            "known_rows": known_rows,
            "remaining_rows": remaining_rows,
            "known_summary": known_summary,
            "remaining_summary": remaining_summary,
            "clean_future_candidates": clean_future_candidates,
        }

    def validate_candidate(self, candidate: SplitV21Candidate) -> SplitV21ValidationResult:
        source = Product.objects.select_related("brand").filter(id=candidate.source_product_id).first()
        blockers: list[str] = []
        notes: list[str] = []

        if source is None:
            return SplitV21ValidationResult(
                case_label=candidate.case_label,
                sku=candidate.sku,
                source_product_id=candidate.source_product_id,
                status=self.STATUS_BLOCKED,
                clean=False,
                blockers=("source_product_not_found",),
                source_catalog_brand="",
                source_display_brand="",
                expected_source_brand=candidate.source_brand_after,
                expected_new_brand=candidate.new_brand_after,
                keep_offer_count=0,
                moved_offer_count=0,
                source_productprice_purchase="",
                expected_source_purchase_from_keep="",
                expected_new_purchase_from_move="",
                source_catalog_brand_norm="",
                expected_source_brand_norm=normalize_brand(candidate.source_brand_after),
                notes="",
            )

        source_offers = list(
            SupplierOffer.objects.select_related("supplier")
            .filter(product=source)
            .order_by("id")
        )
        source_offer_ids = {str(item.id) for item in source_offers}
        move_ids = set(candidate.offers_to_move)
        moved_on_source = [item for item in source_offers if str(item.id) in move_ids]
        keep_offers = [item for item in source_offers if str(item.id) not in move_ids]

        moved_anywhere = list(
            SupplierOffer.objects.select_related("product", "supplier")
            .filter(id__in=list(move_ids))
            .order_by("id")
        )
        moved_missing = sorted(move_ids - {str(item.id) for item in moved_anywhere})
        if moved_missing:
            blockers.append("moved_offer_missing")

        # Already applied pass mode: moved offers are no longer on source and moved together to one other product.
        if move_ids and not moved_on_source:
            target_ids = {str(item.product_id) for item in moved_anywhere}
            if len(target_ids) == 1 and str(source.id) not in target_ids and len(moved_anywhere) == len(move_ids):
                target_id = next(iter(target_ids))
                raw_ok = True
                if candidate.raw_offers_to_move:
                    raw_targets = set(
                        str(item.matched_product_id)
                        for item in SupplierRawOffer.objects.filter(id__in=list(candidate.raw_offers_to_move))
                    )
                    raw_ok = raw_targets == {target_id}
                if raw_ok:
                    return SplitV21ValidationResult(
                        case_label=candidate.case_label,
                        sku=candidate.sku,
                        source_product_id=str(source.id),
                        status=self.STATUS_ALREADY_APPLIED,
                        clean=True,
                        blockers=tuple(),
                        source_catalog_brand=str(source.brand.name if source.brand_id else ""),
                        source_display_brand=str(source.display_brand_name or ""),
                        expected_source_brand=candidate.source_brand_after,
                        expected_new_brand=candidate.new_brand_after,
                        keep_offer_count=len(source_offers),
                        moved_offer_count=0,
                        source_productprice_purchase=self._source_price_purchase(source),
                        expected_source_purchase_from_keep="",
                        expected_new_purchase_from_move="",
                        source_catalog_brand_norm=normalize_brand(str(source.brand.name if source.brand_id else "")),
                        expected_source_brand_norm=normalize_brand(candidate.source_brand_after),
                        notes=f"already applied on product_id={target_id}",
                    )

        if move_ids and not moved_on_source:
            blockers.append("moved_offer_not_on_source")

        if not keep_offers:
            blockers.append("no_keep_offers_after_move")
        if not moved_on_source:
            blockers.append("no_moved_offers_on_source")

        expected_source_norm = normalize_brand(candidate.source_brand_after or candidate.keep_brand_norm)
        expected_new_norm = normalize_brand(candidate.new_brand_after or candidate.move_brand_norm)
        source_norm = normalize_brand(str(source.brand.name if source.brand_id else ""))
        display_norm = normalize_brand(str(source.display_brand_name or ""))

        if expected_source_norm and source_norm != expected_source_norm:
            blockers.append("source_catalog_brand_mismatch_requires_update")
        if expected_source_norm and display_norm and display_norm != expected_source_norm:
            blockers.append("source_display_brand_mismatch_requires_update")

        # Deterministic brand resolution check for source/new expected brands.
        source_brand_candidates = self._brand_candidates(expected_source_norm)
        new_brand_candidates = self._brand_candidates(expected_new_norm)
        if expected_source_norm and len(source_brand_candidates) != 1:
            blockers.append("source_catalog_brand_unresolved")
        if expected_new_norm and len(new_brand_candidates) != 1:
            blockers.append("new_catalog_brand_unresolved")
            blockers.append("move_brand_not_resolved")

        # Keep validator consistent with final split planner gate:
        # planner requires deterministic new Auto_DB supplier resolution
        # from source autodb binding for moved-brand side.
        new_autodb_id_after, _new_autodb_name_after = self._resolve_new_autodb_after(
            source=source,
            move_brand_norm=expected_new_norm,
        )
        if expected_new_norm and new_autodb_id_after is None:
            blockers.append("brand_display_conflict_unresolved_new_autodb_supplier")
            blockers.append("missing_deterministic_supplier_candidate")

        source_pp_qs = ProductPrice.objects.filter(product=source).order_by("id")
        source_pp_rows = list(source_pp_qs)
        source_pp_purchase = ""
        expected_source_purchase = ""
        expected_new_purchase = ""
        if len(source_pp_rows) != 1:
            blockers.append("source_productprice_ambiguous")
        else:
            source_pp_purchase = str(source_pp_rows[0].purchase_price)
            if len(keep_offers) == 1:
                expected_source_purchase = str(keep_offers[0].purchase_price)
                if Decimal(str(source_pp_rows[0].purchase_price)) != Decimal(str(keep_offers[0].purchase_price)):
                    blockers.append("source_productprice_basis_mismatch")
            else:
                blockers.append("source_productprice_basis_ambiguous_multi_keep")

            if len(moved_on_source) == 1:
                expected_new_purchase = str(moved_on_source[0].purchase_price)
                # v2 baseline behavior kept source ProductPrice row unchanged; block if it equals moved value rather than keep.
                if expected_source_purchase and Decimal(str(source_pp_rows[0].purchase_price)) == Decimal(
                    str(moved_on_source[0].purchase_price)
                ) and Decimal(str(moved_on_source[0].purchase_price)) != Decimal(str(keep_offers[0].purchase_price if keep_offers else "0")):
                    blockers.append("old_price_basis_would_remain_on_source")
            else:
                blockers.append("new_productprice_basis_ambiguous_multi_move")

        moved_supplier_ids = {int(item.supplier_id) for item in moved_on_source}
        keep_supplier_ids = {int(item.supplier_id) for item in keep_offers}
        raw_all = list(
            SupplierRawOffer.objects.filter(matched_product=source).select_related("supplier", "source").order_by("id")
        )

        if candidate.raw_offers_to_move:
            raw_move_rows = [item for item in raw_all if str(item.id) in set(candidate.raw_offers_to_move)]
            if len(raw_move_rows) != len(set(candidate.raw_offers_to_move)):
                blockers.append("raw_offer_not_on_source_for_move_set")
            for row in raw_move_rows:
                if int(row.supplier_id) not in moved_supplier_ids:
                    blockers.append("raw_offer_supplier_mismatch_with_moved_offer")
        else:
            raw_move_rows = []

        # For every moved offer, require deterministic raw evidence.
        for offer in moved_on_source:
            sku_norm = _canonical_article(str(offer.supplier_sku or ""))
            matched = [
                row
                for row in raw_all
                if int(row.supplier_id) == int(offer.supplier_id)
                and (
                    _canonical_article(str(row.article or "")) == sku_norm
                    or _canonical_article(str(row.external_sku or "")) == sku_norm
                    or _canonical_article(str(row.normalized_article or "")) == sku_norm
                )
            ]
            if not matched:
                blockers.append("raw_offer_mismatch_for_moved_offer")

        keep_raw_norms = {
            normalize_brand(str(row.brand_name or ""))
            for row in raw_all
            if int(row.supplier_id) in keep_supplier_ids
        }
        move_raw_norms = {
            normalize_brand(str(row.brand_name or ""))
            for row in raw_all
            if int(row.supplier_id) in moved_supplier_ids
        }
        if expected_source_norm and keep_raw_norms and expected_source_norm not in keep_raw_norms:
            blockers.append("source_group_brand_evidence_mismatch")
        if expected_new_norm and move_raw_norms and expected_new_norm not in move_raw_norms:
            blockers.append("moved_group_brand_evidence_mismatch")

        # Warehouse/source simulation: moved + keep raw source codes should be separable.
        keep_raw_sources = {
            str(row.source.code or "").strip().lower()
            for row in raw_all
            if int(row.supplier_id) in keep_supplier_ids
        }
        move_raw_sources = {
            str(row.source.code or "").strip().lower()
            for row in raw_all
            if int(row.supplier_id) in moved_supplier_ids
        }
        if keep_raw_sources and move_raw_sources and keep_raw_sources == move_raw_sources:
            blockers.append("warehouse_source_split_not_separable")

        if "source_catalog_brand_mismatch_requires_update" in blockers and "source_productprice_basis_mismatch" in blockers:
            notes.append("brand_and_productprice_basis_mismatch_like_4S5V3O6M6442")

        status = self.STATUS_CLEAN if not blockers else self.STATUS_BLOCKED
        return SplitV21ValidationResult(
            case_label=candidate.case_label,
            sku=candidate.sku,
            source_product_id=str(source.id),
            status=status,
            clean=not blockers,
            blockers=tuple(sorted(set(blockers))),
            source_catalog_brand=str(source.brand.name if source.brand_id else ""),
            source_display_brand=str(source.display_brand_name or ""),
            expected_source_brand=candidate.source_brand_after,
            expected_new_brand=candidate.new_brand_after,
            keep_offer_count=len(keep_offers),
            moved_offer_count=len(moved_on_source),
            source_productprice_purchase=source_pp_purchase,
            expected_source_purchase_from_keep=expected_source_purchase,
            expected_new_purchase_from_move=expected_new_purchase,
            source_catalog_brand_norm=source_norm,
            expected_source_brand_norm=expected_source_norm,
            notes=";".join(notes),
        )

    def _source_price_purchase(self, source: Product) -> str:
        row = ProductPrice.objects.filter(product=source).only("purchase_price").first()
        if row is None:
            return ""
        return str(row.purchase_price)

    def _brand_candidates(self, normalized: str) -> list[Brand]:
        if not normalized:
            return []
        return [item for item in Brand.objects.only("id", "name").all() if normalize_brand(str(item.name or "")) == normalized]

    def _resolve_new_autodb_after(self, *, source: Product, move_brand_norm: str) -> tuple[int | None, str]:
        current_name = str(source.autodb_supplier_name or "")
        current_norm = normalize_brand(current_name)
        if move_brand_norm and move_brand_norm == current_norm:
            return int(source.autodb_supplier_id or 0) or None, current_name
        return None, ""

    def _known_case_candidates(self) -> list[SplitV21Candidate]:
        rows: list[SplitV21Candidate] = []

        known_1 = _load_csv(self.KNOWN_CASE_1)
        if known_1:
            row = known_1[0]
            rows.append(
                self._candidate_from_plan_row(
                    case_label="case_1_0S3V5O5M9202",
                    row=row,
                )
            )

        known_2 = _load_csv(self.KNOWN_CASE_2)
        if known_2:
            row = known_2[0]
            rows.append(
                self._candidate_from_plan_row(
                    case_label="case_2_4S5V3O6M6442",
                    row=row,
                )
            )
        return rows

    def _remaining_candidates(self) -> list[SplitV21Candidate]:
        rows: list[SplitV21Candidate] = []
        for row in _load_csv(self.REMAINING_CANDIDATES):
            decision = str(row.get("decision") or "").strip()
            if decision not in {"selected_candidate", "not_selected_by_limit"}:
                continue
            case_label = f"remaining:{row.get('product_id','')}"
            rows.append(
                SplitV21Candidate(
                    case_label=case_label,
                    sku=str(row.get("original_sku") or ""),
                    source_product_id=str(row.get("product_id") or ""),
                    keep_group=str(row.get("keep_group") or ""),
                    move_group=str(row.get("move_group") or ""),
                    keep_brand_norm=normalize_brand(str(row.get("keep_group") or "").split("|", 1)[0]),
                    move_brand_norm=normalize_brand(str(row.get("move_group") or "").split("|", 1)[0]),
                    source_brand_after=str(row.get("keep_group") or "").split("|", 1)[0].strip(),
                    source_display_brand_after=str(row.get("keep_group") or "").split("|", 1)[0].strip(),
                    new_brand_after=str(row.get("move_group") or "").split("|", 1)[0].strip(),
                    new_display_brand_after=str(row.get("move_group") or "").split("|", 1)[0].strip(),
                    offers_to_move=tuple(sorted({item.strip() for item in str(row.get("supplier_offer_ids_to_move") or "").split(",") if item.strip()})),
                    raw_offers_to_move=tuple(sorted({item.strip() for item in str(row.get("supplier_raw_offer_ids_to_move") or "").split(",") if item.strip()})),
                    source_productprice_ids=tuple(),
                )
            )
        return rows

    def _candidate_from_plan_row(self, *, case_label: str, row: dict[str, str]) -> SplitV21Candidate:
        return SplitV21Candidate(
            case_label=case_label,
            sku=str(row.get("sku") or ""),
            source_product_id=str(row.get("source_product_id") or ""),
            keep_group=str(row.get("keep_group") or ""),
            move_group=str(row.get("move_group") or ""),
            keep_brand_norm=str(row.get("keep_brand_norm") or ""),
            move_brand_norm=str(row.get("move_brand_norm") or ""),
            source_brand_after=str(row.get("source_brand_after") or ""),
            source_display_brand_after=str(row.get("source_display_brand_after") or ""),
            new_brand_after=str(row.get("new_brand_after") or ""),
            new_display_brand_after=str(row.get("new_display_brand_after") or ""),
            offers_to_move=_as_tuple_ids(str(row.get("offers_to_move") or "")),
            raw_offers_to_move=_as_tuple_ids(str(row.get("raw_offers_to_move") or "")),
            source_productprice_ids=_as_tuple_ids(str(row.get("source_productprice_ids") or "")),
        )
