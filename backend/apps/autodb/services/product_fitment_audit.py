from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import csv
from pathlib import Path
import random
from statistics import median
from typing import Any

from django.db.models import Prefetch

from apps.autodb.services.column_helpers import find_column_name, find_value
from apps.autodb.services.fitment_quality import AutoDbProductLinkQualityService, ProductFitmentQualityService
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.catalog.models import Product
from apps.compatibility.models import ProductFitment


@dataclass(frozen=True)
class ProductFitmentAuditRow:
    product_id: str
    name_uk: str
    name_ru: str
    name_en: str
    brand: str
    article: str
    autodb_article_key: str
    autodb_article_title: str
    autodb_prd_title: str
    fitment_count: int
    stale_fitment_count: int
    sample_autodb_passanger_car_id: int | None
    sample_vehicle_label: str
    suspicious_flags: tuple[str, ...]
    suspicious_reason: str
    raw_linkage_type_counts: dict[str, int]
    missing_passanger_car_ids: tuple[int, ...]
    persisted_quality_status: str = ""
    persisted_quality_reason: str = ""
    persisted_excluded_from_public_filtering: bool = False
    persisted_manual_override: bool = False


@dataclass(frozen=True)
class ProductFitmentAuditSummary:
    audited_products: int
    total_fitments: int
    min_fitments: int
    max_fitments: int
    avg_fitments: float
    median_fitments: float
    suspicious_products: int
    products_over_1000_fitments: tuple[tuple[str, str, int], ...]
    top_products: tuple[tuple[str, str, int], ...]
    linkage_type_counts: dict[str, int]
    autodb_fitment_linkage_counts: dict[str, int]
    missing_passanger_car_count: int
    sample_rows: tuple[ProductFitmentAuditRow, ...]


class AutoDbProductFitmentAuditService:
    def __init__(
        self,
        *,
        storage: AutoDbRawCloneStorage | None = None,
        quality_service: ProductFitmentQualityService | None = None,
        link_quality_service: AutoDbProductLinkQualityService | None = None,
    ):
        self.storage = storage or AutoDbRawCloneStorage()
        self.quality_service = quality_service or ProductFitmentQualityService()
        self.link_quality_service = link_quality_service or AutoDbProductLinkQualityService()

    def build_queryset(
        self,
        *,
        limit: int = 0,
        product_id: str = "",
        sample: int = 0,
    ):
        fitments_qs = ProductFitment.objects.filter(source=ProductFitment.SOURCE_AUTODB_PRO).order_by(
            "autodb_passanger_car_id", "id"
        )
        queryset = (
            Product.objects.filter(fitments__source=ProductFitment.SOURCE_AUTODB_PRO)
            .distinct()
            .select_related("category")
            .prefetch_related(Prefetch("fitments", queryset=fitments_qs, to_attr="autodb_fitments"))
            .order_by("id")
        )
        if product_id:
            return queryset.filter(pk=product_id)
        if sample > 0:
            ids = list(queryset.values_list("id", flat=True))
            if not ids:
                return queryset.none()
            random.seed(0)
            chosen = random.sample(ids, min(sample, len(ids)))
            return queryset.filter(id__in=chosen).order_by("id")
        if limit > 0:
            return queryset[:limit]
        return queryset

    def audit_queryset(
        self,
        queryset,
        *,
        persist_quality: bool = False,
    ) -> tuple[list[ProductFitmentAuditRow], ProductFitmentAuditSummary]:
        products = list(queryset)
        car_ids = sorted(
            {
                int(fitment.autodb_passanger_car_id)
                for product in products
                for fitment in getattr(product, "autodb_fitments", [])
                if fitment.autodb_passanger_car_id is not None
            }
        )
        cars = self._find_passanger_car_contexts(linkage_ids=set(car_ids))

        rows: list[ProductFitmentAuditRow] = []
        linkage_type_counts: Counter[str] = Counter()
        autodb_fitment_linkage_counts: Counter[str] = Counter()
        missing_passanger_car_ids: set[int] = set()

        for product in products:
            fitments = list(getattr(product, "autodb_fitments", []))
            for fitment in fitments:
                linkage_type = str(fitment.linkage_type or "") or "-"
                autodb_fitment_linkage_counts[linkage_type] += 1

            article_row = self._find_article_row(
                supplier_id=self._safe_int(getattr(product, "autodb_supplier_id", None)),
                article_number=str(getattr(product, "autodb_article_number", "") or "").strip(),
            )
            article_title = self._extract_article_title(article_row)
            prd_title = self._resolve_prd_title(
                supplier_id=self._safe_int(getattr(product, "autodb_supplier_id", None)),
                article_number=str(getattr(product, "autodb_article_number", "") or "").strip(),
            )
            quality = self.quality_service.evaluate(
                product=product,
                autodb_article_title=article_title,
                autodb_prd_title=prd_title,
            )

            article_li_rows = self._find_article_li_rows(
                supplier_id=self._safe_int(getattr(product, "autodb_supplier_id", None)),
                article_number=str(getattr(product, "autodb_article_number", "") or "").strip(),
            )
            raw_linkage_counts: Counter[str] = Counter()
            row_missing_passanger_car_ids: set[int] = set()
            for item in article_li_rows:
                linkage_type = str(find_value(item, ["linkageTypeId", "linkagetypeid", "LinkageTypeId"]) or "").strip() or "-"
                raw_linkage_counts[linkage_type] += 1
                linkage_type_counts[linkage_type] += 1
                if linkage_type.lower() != "passengercar":
                    continue
                linkage_id = self._safe_int(find_value(item, ["linkageId", "linkageid", "LinkageId"]))
                if linkage_id is not None and linkage_id not in cars:
                    missing_passanger_car_ids.add(linkage_id)
                    row_missing_passanger_car_ids.add(linkage_id)

            active_fitments = [item for item in fitments if not item.is_stale]
            fitment_count = len(active_fitments)
            stale_fitment_count = sum(1 for item in fitments if item.is_stale)
            sample_fitment = active_fitments[0] if active_fitments else (fitments[0] if fitments else None)
            sample_car_id = self._safe_int(getattr(sample_fitment, "autodb_passanger_car_id", None)) if sample_fitment else None
            sample_car = cars.get(sample_car_id) if sample_car_id is not None else None
            sample_vehicle_label = self._build_vehicle_label(sample_car) if sample_car is not None else ""

            suspicious_flags: list[str] = []
            if quality.suspicious_link:
                suspicious_flags.append("suspicious_link")
            if fitment_count > 1000:
                suspicious_flags.append("fitment_count_gt_1000")
            if stale_fitment_count > 0:
                suspicious_flags.append("stale_fitments_present")
            if not article_title:
                suspicious_flags.append("missing_article_title")
            if not prd_title:
                suspicious_flags.append("missing_prd_title")

            persisted_quality_status = ""
            persisted_quality_reason = ""
            persisted_excluded_from_public_filtering = False
            persisted_manual_override = False
            if persist_quality:
                persisted = self.link_quality_service.persist_audit_result(
                    product=product,
                    suspicious_flags=tuple(suspicious_flags),
                    suspicious_reason=quality.suspicious_reason,
                    evidence={
                        "autodb_article_key": str(getattr(product, "autodb_article_key", "") or ""),
                        "autodb_article_title": article_title,
                        "autodb_prd_title": prd_title,
                        "fitment_count": fitment_count,
                        "stale_fitment_count": stale_fitment_count,
                        "suspicious_flags": list(suspicious_flags),
                        "suspicious_reason": quality.suspicious_reason,
                        "raw_linkage_type_counts": dict(raw_linkage_counts),
                        "missing_passanger_car_ids": sorted(row_missing_passanger_car_ids),
                    },
                )
                persisted_quality_status = persisted.status
                persisted_quality_reason = persisted.reason
                persisted_excluded_from_public_filtering = persisted.excluded_from_public_filtering
                persisted_manual_override = persisted.manually_confirmed

            rows.append(
                ProductFitmentAuditRow(
                    product_id=str(product.id),
                    name_uk=str(getattr(product, "name_uk", "") or ""),
                    name_ru=str(getattr(product, "name_ru", "") or ""),
                    name_en=str(getattr(product, "name_en", "") or ""),
                    brand=str(getattr(getattr(product, "brand", None), "name", "") or ""),
                    article=str(getattr(product, "article", "") or ""),
                    autodb_article_key=str(getattr(product, "autodb_article_key", "") or ""),
                    autodb_article_title=article_title,
                    autodb_prd_title=prd_title,
                    fitment_count=fitment_count,
                    stale_fitment_count=stale_fitment_count,
                    sample_autodb_passanger_car_id=sample_car_id,
                    sample_vehicle_label=sample_vehicle_label,
                    suspicious_flags=tuple(suspicious_flags),
                    suspicious_reason=quality.suspicious_reason,
                    raw_linkage_type_counts=dict(raw_linkage_counts),
                    missing_passanger_car_ids=tuple(sorted(row_missing_passanger_car_ids)),
                    persisted_quality_status=persisted_quality_status,
                    persisted_quality_reason=persisted_quality_reason,
                    persisted_excluded_from_public_filtering=persisted_excluded_from_public_filtering,
                    persisted_manual_override=persisted_manual_override,
                )
            )

        summary = self._build_summary(
            rows=rows,
            linkage_type_counts=dict(linkage_type_counts),
            autodb_fitment_linkage_counts=dict(autodb_fitment_linkage_counts),
            missing_passanger_car_count=len(missing_passanger_car_ids),
        )
        return rows, summary

    def export_csv(self, *, rows: list[ProductFitmentAuditRow], path: str) -> str:
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "product_id",
                    "name_uk",
                    "name_ru",
                    "name_en",
                    "brand",
                    "article",
                    "autodb_article_key",
                    "autodb_article_title",
                    "autodb_prd_title",
                    "fitment_count",
                    "stale_fitment_count",
                    "sample_autodb_passanger_car_id",
                    "sample_vehicle_label",
                    "suspicious_flags",
                    "suspicious_reason",
                ]
            )
            for row in rows:
                writer.writerow(
                    [
                        row.product_id,
                        row.name_uk,
                        row.name_ru,
                        row.name_en,
                        row.brand,
                        row.article,
                        row.autodb_article_key,
                        row.autodb_article_title,
                        row.autodb_prd_title,
                        row.fitment_count,
                        row.stale_fitment_count,
                        row.sample_autodb_passanger_car_id or "",
                        row.sample_vehicle_label,
                        ",".join(row.suspicious_flags),
                        row.suspicious_reason,
                    ]
                )
        return str(target)

    def _build_summary(
        self,
        *,
        rows: list[ProductFitmentAuditRow],
        linkage_type_counts: dict[str, int],
        autodb_fitment_linkage_counts: dict[str, int],
        missing_passanger_car_count: int,
    ) -> ProductFitmentAuditSummary:
        counts = [row.fitment_count for row in rows]
        total_fitments = sum(counts)
        min_fitments = min(counts) if counts else 0
        max_fitments = max(counts) if counts else 0
        avg_fitments = round(total_fitments / len(counts), 2) if counts else 0.0
        median_fitments = float(median(counts)) if counts else 0.0
        suspicious_products = sum(1 for row in rows if "suspicious_link" in row.suspicious_flags)
        top_products = tuple(
            (row.product_id, row.name_uk or row.name_ru or row.name_en, row.fitment_count)
            for row in sorted(rows, key=lambda item: (-item.fitment_count, item.product_id))[:20]
        )
        products_over_1000_fitments = tuple(item for item in top_products if item[2] > 1000)
        sample_rows = tuple(sorted(rows, key=lambda item: item.product_id)[:10])
        return ProductFitmentAuditSummary(
            audited_products=len(rows),
            total_fitments=total_fitments,
            min_fitments=min_fitments,
            max_fitments=max_fitments,
            avg_fitments=avg_fitments,
            median_fitments=median_fitments,
            suspicious_products=suspicious_products,
            products_over_1000_fitments=products_over_1000_fitments,
            top_products=top_products,
            linkage_type_counts=linkage_type_counts,
            autodb_fitment_linkage_counts=autodb_fitment_linkage_counts,
            missing_passanger_car_count=missing_passanger_car_count,
            sample_rows=sample_rows,
        )

    def _find_article_li_rows(self, *, supplier_id: int | None, article_number: str) -> list[dict[str, Any]]:
        if supplier_id is None or supplier_id <= 0 or not article_number:
            return []
        self.storage.ensure_table("article_li")
        columns = list(self.storage.get_local_columns("article_li"))
        if not columns:
            return []
        supplier_column = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id"])
        article_column = find_column_name(
            columns,
            ["DataSupplierArticleNumber", "datasupplierarticlenumber", "dataSupplierArticleNumber", "article", "articlenumber"],
        )
        if not supplier_column or not article_column:
            return []
        exact_rows = self.storage.fetch_local_rows(
            table="article_li",
            filters={supplier_column: supplier_id, article_column: article_number},
            limit=2000,
            columns=columns,
        )
        if exact_rows:
            return exact_rows
        supplier_rows = self.storage.fetch_local_rows(
            table="article_li",
            filters={supplier_column: supplier_id},
            limit=10000,
            columns=columns,
        )
        target = article_number.strip().lower()
        return [
            row
            for row in supplier_rows
            if str(find_value(row, [article_column]) or "").strip().lower() == target
        ]

    def _find_article_row(self, *, supplier_id: int | None, article_number: str) -> dict[str, Any] | None:
        if supplier_id is None or supplier_id <= 0 or not article_number:
            return None
        self.storage.ensure_table("articles")
        columns = list(self.storage.get_local_columns("articles"))
        if not columns:
            return None
        supplier_column = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id"])
        article_column = find_column_name(
            columns,
            ["DataSupplierArticleNumber", "datasupplierarticlenumber", "article", "articlenumber", "number"],
        )
        if not supplier_column or not article_column:
            return None
        rows = self.storage.fetch_local_rows(
            table="articles",
            filters={supplier_column: supplier_id, article_column: article_number},
            limit=1,
            columns=columns,
        )
        return dict(rows[0]) if rows else None

    def _find_article_prd_rows(self, *, supplier_id: int | None, article_number: str) -> list[dict[str, Any]]:
        if supplier_id is None or supplier_id <= 0 or not article_number:
            return []
        self.storage.ensure_table("article_prd")
        columns = list(self.storage.get_local_columns("article_prd"))
        supplier_column = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id"])
        article_column = find_column_name(
            columns,
            ["DataSupplierArticleNumber", "datasupplierarticlenumber", "article", "articlenumber", "number"],
        )
        if not supplier_column or not article_column:
            return []
        return self.storage.fetch_local_rows(
            table="article_prd",
            filters={supplier_column: supplier_id, article_column: article_number},
            limit=300,
            columns=columns,
        )

    def _find_article_links_rows(self, *, supplier_id: int | None, article_number: str) -> list[dict[str, Any]]:
        if supplier_id is None or supplier_id <= 0 or not article_number:
            return []
        self.storage.ensure_table("article_links")
        columns = list(self.storage.get_local_columns("article_links"))
        supplier_column = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id"])
        article_column = find_column_name(
            columns,
            ["DataSupplierArticleNumber", "datasupplierarticlenumber", "article", "articlenumber", "number"],
        )
        if not supplier_column or not article_column:
            return []
        return self.storage.fetch_local_rows(
            table="article_links",
            filters={supplier_column: supplier_id, article_column: article_number},
            limit=300,
            columns=columns,
        )

    def _find_prd_rows(self, *, product_ids: list[int]) -> list[dict[str, Any]]:
        if not product_ids:
            return []
        self.storage.ensure_table("prd")
        columns = list(self.storage.get_local_columns("prd"))
        if not columns:
            return []
        id_column = find_column_name(columns, ["id", "productId", "productid", "ProductId", "prdid"])
        if not id_column:
            return []
        return self.storage.fetch_local_rows_in(
            table="prd",
            column=id_column,
            values=product_ids,
            limit=max(100, len(product_ids) * 2),
            columns=columns,
        )

    def _resolve_prd_title(self, *, supplier_id: int | None, article_number: str) -> str:
        article_prd_rows = self._find_article_prd_rows(supplier_id=supplier_id, article_number=article_number)
        article_links_rows = self._find_article_links_rows(supplier_id=supplier_id, article_number=article_number)
        product_ids: list[int] = []
        for row in article_prd_rows + article_links_rows:
            prd_id = self._safe_int(find_value(row, ["productId", "productid", "ProductId", "prdid", "prdId", "id"]))
            if prd_id is None or prd_id in product_ids:
                continue
            product_ids.append(prd_id)
        prd_rows = self._find_prd_rows(product_ids=product_ids)
        for row in prd_rows:
            title = self._extract_prd_title(row)
            if title:
                return title
        return ""

    def _extract_article_title(self, row: dict[str, Any] | None) -> str:
        payload = row or {}
        for key in ["normalizeddescription", "NormalizedDescription", "description", "Description"]:
            value = str(find_value(payload, [key]) or "").strip()
            if value:
                return value[:255]
        return ""

    def _extract_prd_title(self, row: dict[str, Any]) -> str:
        for key in ["fulldescription", "fullDescription", "normalizeddescription", "NormalizedDescription", "description", "Description"]:
            value = str(find_value(row, [key]) or "").strip()
            if value:
                return value[:255]
        return ""

    def _find_passanger_car_contexts(self, *, linkage_ids: set[int]) -> dict[int, dict[str, Any]]:
        if not linkage_ids:
            return {}
        self.storage.ensure_table("passanger_cars")
        car_columns = list(self.storage.get_local_columns("passanger_cars"))
        if not car_columns:
            return {}
        car_id_column = find_column_name(car_columns, ["id", "ID"])
        if not car_id_column:
            return {}
        car_rows = self.storage.fetch_local_rows_in(
            table="passanger_cars",
            column=car_id_column,
            values=sorted(linkage_ids),
            limit=max(100, len(linkage_ids) * 2),
            columns=car_columns,
        )

        model_ids = sorted(
            {
                model_id
                for row in car_rows
                if (model_id := self._safe_int(find_value(row, ["modelid", "modelId", "ModelId"]))) is not None
            }
        )
        model_contexts = self._find_model_contexts(model_ids=model_ids)

        contexts: dict[int, dict[str, Any]] = {}
        for row in car_rows:
            car_id = self._safe_int(find_value(row, [car_id_column, "id", "ID"]))
            if car_id is None:
                continue
            model_id = self._safe_int(find_value(row, ["modelid", "modelId", "ModelId"]))
            model_context = model_contexts.get(model_id or -1, {})
            contexts[car_id] = {
                "id": car_id,
                "make": str(model_context.get("manufacturer_description", "") or "").strip(),
                "model": str(model_context.get("description", "") or "").strip(),
                "full_description": str(
                    find_value(row, ["fulldescription", "fullDescription", "FullDescription", "description", "Description"]) or ""
                ).strip(),
                "description": str(find_value(row, ["description", "Description"]) or "").strip(),
                "construction_interval": str(
                    find_value(row, ["constructioninterval", "constructionInterval", "ConstructionInterval"]) or ""
                ).strip(),
            }
        return contexts

    def _find_model_contexts(self, *, model_ids: list[int]) -> dict[int, dict[str, Any]]:
        if not model_ids:
            return {}
        self.storage.ensure_table("models")
        model_columns = list(self.storage.get_local_columns("models"))
        if not model_columns:
            return {}
        model_id_column = find_column_name(model_columns, ["id", "ID"])
        if not model_id_column:
            return {}
        model_rows = self.storage.fetch_local_rows_in(
            table="models",
            column=model_id_column,
            values=model_ids,
            limit=max(100, len(model_ids) * 2),
            columns=model_columns,
        )
        manufacturer_ids = sorted(
            {
                manufacturer_id
                for row in model_rows
                if (
                    manufacturer_id := self._safe_int(
                        find_value(row, ["manufacturerid", "manufacturerId", "ManufacturerId"])
                    )
                )
                is not None
            }
        )
        manufacturers = self._find_manufacturer_contexts(manufacturer_ids=manufacturer_ids)

        contexts: dict[int, dict[str, Any]] = {}
        for row in model_rows:
            model_id = self._safe_int(find_value(row, [model_id_column, "id", "ID"]))
            if model_id is None:
                continue
            manufacturer_id = self._safe_int(find_value(row, ["manufacturerid", "manufacturerId", "ManufacturerId"]))
            manufacturer_context = manufacturers.get(manufacturer_id or -1, {})
            contexts[model_id] = {
                "id": model_id,
                "description": str(
                    find_value(row, ["description", "Description", "fulldescription", "fullDescription"]) or ""
                ).strip(),
                "manufacturer_description": str(
                    manufacturer_context.get("description") or manufacturer_context.get("fulldescription") or ""
                ).strip(),
            }
        return contexts

    def _find_manufacturer_contexts(self, *, manufacturer_ids: list[int]) -> dict[int, dict[str, Any]]:
        if not manufacturer_ids:
            return {}
        self.storage.ensure_table("manufacturers")
        manufacturer_columns = list(self.storage.get_local_columns("manufacturers"))
        if not manufacturer_columns:
            return {}
        manufacturer_id_column = find_column_name(manufacturer_columns, ["id", "ID"])
        if not manufacturer_id_column:
            return {}
        manufacturer_rows = self.storage.fetch_local_rows_in(
            table="manufacturers",
            column=manufacturer_id_column,
            values=manufacturer_ids,
            limit=max(100, len(manufacturer_ids) * 2),
            columns=manufacturer_columns,
        )
        contexts: dict[int, dict[str, Any]] = {}
        for row in manufacturer_rows:
            manufacturer_id = self._safe_int(find_value(row, [manufacturer_id_column, "id", "ID"]))
            if manufacturer_id is None:
                continue
            contexts[manufacturer_id] = {
                "id": manufacturer_id,
                "description": str(find_value(row, ["description", "Description"]) or "").strip(),
                "fulldescription": str(find_value(row, ["fulldescription", "fullDescription", "FullDescription"]) or "").strip(),
            }
        return contexts

    def _build_vehicle_label(self, car: dict[str, Any]) -> str:
        make = str(car.get("make", "") or "").strip()
        model = str(car.get("model", "") or "").strip()
        modification = str(car.get("full_description", "") or car.get("description", "") or "").strip()
        period = str(car.get("construction_interval", "") or "").strip()
        return " / ".join(item for item in [make, model, modification, period] if item)

    def _safe_int(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
