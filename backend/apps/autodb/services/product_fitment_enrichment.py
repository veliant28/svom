from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
import json
from typing import Any

from django.db.models import F

from apps.autodb.services.column_helpers import find_column_name, find_value
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.catalog.models import AutoDbProductLinkQuality, Product
from apps.compatibility.models import ProductFitment


@dataclass(frozen=True)
class ProductFitmentEnrichmentResult:
    product_id: str
    status: str
    has_fitments: bool
    fitments_created: int
    fitments_updated: int
    stale_marked: int
    skipped_no_autodb_link: bool
    skipped_no_article_li: bool
    skipped_non_passenger_car: bool
    skipped_missing_passanger_car: bool
    skipped_manual_locked: bool
    error: str = ""


@dataclass(frozen=True)
class ProductFitmentDiagnostics:
    product_id: str
    bridge_supplier_id: int | None
    bridge_article_number: str
    bridge_article_key: str
    article_li_rows: tuple[dict[str, Any], ...]
    passenger_candidates: tuple[dict[str, Any], ...]
    passanger_cars_rows: tuple[dict[str, Any], ...]
    current_fitments: tuple[dict[str, Any], ...]
    proposed_creates: tuple[dict[str, Any], ...]
    proposed_updates: tuple[dict[str, Any], ...]
    proposed_stale: tuple[dict[str, Any], ...]
    skipped_reason: str


class AutoDbProductFitmentEnrichmentService:
    LINKAGE_TYPE_PASSENGER_CAR = "PassengerCar"

    def __init__(self, *, storage: AutoDbRawCloneStorage | None = None):
        self.storage = storage or AutoDbRawCloneStorage()

    def build_queryset(self, *, product_id: str = "", only_linked: bool = False, only_trusted: bool = False):
        qs = Product.objects.select_related("brand", "category").order_by("id")
        if only_linked:
            qs = qs.filter(autodb_supplier_id__isnull=False).exclude(autodb_article_number="")
        if only_trusted:
            qs = qs.filter(
                autodb_link_qualities__status=AutoDbProductLinkQuality.STATUS_TRUSTED,
                autodb_link_qualities__autodb_article_key=F("autodb_article_key"),
            )
        if product_id:
            qs = qs.filter(pk=product_id)
        return qs.distinct()

    def enrich_product(self, *, product: Product, dry_run: bool) -> ProductFitmentEnrichmentResult:
        supplier_id = self._safe_int(getattr(product, "autodb_supplier_id", None))
        article_number = str(getattr(product, "autodb_article_number", "") or "").strip()
        article_key = str(getattr(product, "autodb_article_key", "") or "").strip()
        if supplier_id is None or not article_number:
            return ProductFitmentEnrichmentResult(
                product_id=str(product.id),
                status="skipped_no_autodb_link",
                has_fitments=False,
                fitments_created=0,
                fitments_updated=0,
                stale_marked=0,
                skipped_no_autodb_link=True,
                skipped_no_article_li=False,
                skipped_non_passenger_car=False,
                skipped_missing_passanger_car=False,
                skipped_manual_locked=False,
            )

        article_rows = self._find_article_li_rows(supplier_id=supplier_id, article_number=article_number)
        if not article_rows:
            stale_marked = self._mark_missing_as_stale(
                product=product,
                active_linkage_keys=set(),
                dry_run=dry_run,
            )
            return ProductFitmentEnrichmentResult(
                product_id=str(product.id),
                status="skipped_no_article_li",
                has_fitments=False,
                fitments_created=0,
                fitments_updated=0,
                stale_marked=stale_marked,
                skipped_no_autodb_link=False,
                skipped_no_article_li=True,
                skipped_non_passenger_car=False,
                skipped_missing_passanger_car=False,
                skipped_manual_locked=False,
            )

        linkage_rows: list[tuple[str, int, dict[str, Any]]] = []
        passenger_linkage_ids: set[int] = set()
        for row in article_rows:
            linkage_id = self._safe_int(find_value(row, ["linkageId", "linkageid", "LinkageId"]))
            if linkage_id is None or linkage_id <= 0:
                continue
            linkage_type = self._normalize_linkage_type(find_value(row, ["linkageTypeId", "linkagetypeid", "LinkageTypeId"]))
            if self._is_passenger_linkage(linkage_type):
                passenger_linkage_ids.add(linkage_id)
            linkage_rows.append((linkage_type, linkage_id, row))

        if not linkage_rows:
            stale_marked = self._mark_missing_as_stale(
                product=product,
                active_linkage_keys=set(),
                dry_run=dry_run,
            )
            return ProductFitmentEnrichmentResult(
                product_id=str(product.id),
                status="skipped_non_passenger_car",
                has_fitments=False,
                fitments_created=0,
                fitments_updated=0,
                stale_marked=stale_marked,
                skipped_no_autodb_link=False,
                skipped_no_article_li=False,
                skipped_non_passenger_car=True,
                skipped_missing_passanger_car=False,
                skipped_manual_locked=False,
            )

        existing_car_ids = self._find_existing_passanger_car_ids(linkage_ids=passenger_linkage_ids)
        valid_linkage_rows: list[tuple[str, int, dict[str, Any]]] = []
        for linkage_type, linkage_id, row in linkage_rows:
            if self._is_passenger_linkage(linkage_type) and linkage_id not in existing_car_ids:
                continue
            valid_linkage_rows.append((linkage_type, linkage_id, row))
        if not valid_linkage_rows:
            stale_marked = self._mark_missing_as_stale(
                product=product,
                active_linkage_keys=set(),
                dry_run=dry_run,
            )
            return ProductFitmentEnrichmentResult(
                product_id=str(product.id),
                status="skipped_missing_passanger_car",
                has_fitments=False,
                fitments_created=0,
                fitments_updated=0,
                stale_marked=stale_marked,
                skipped_no_autodb_link=False,
                skipped_no_article_li=False,
                skipped_non_passenger_car=False,
                skipped_missing_passanger_car=True,
                skipped_manual_locked=False,
            )

        existing_fitments = list(
            ProductFitment.objects.filter(
                product=product,
                source=ProductFitment.SOURCE_AUTODB_PRO,
            ).order_by("id")
        )
        by_linkage_key = {
            (self._linkage_type_key(item.linkage_type), int(item.autodb_passanger_car_id)): item
            for item in existing_fitments
            if item.autodb_passanger_car_id is not None
        }

        created = 0
        updated = 0
        skipped_manual_locked = False

        active_linkage_keys = {
            (self._linkage_type_key(linkage_type), linkage_id)
            for linkage_type, linkage_id, _ in valid_linkage_rows
        }
        for linkage_type, linkage_id, row in valid_linkage_rows:
            linkage_type_value = linkage_type or self.LINKAGE_TYPE_PASSENGER_CAR
            source_payload = {
                "source": ProductFitment.SOURCE_AUTODB_PRO,
                "linkage_type": linkage_type_value,
                "linkage_id": linkage_id,
                "supplier_id": supplier_id,
                "article_number": article_number,
                "article_key": article_key,
                "raw": self._trim_article_li_row(row),
            }
            source_hash = self._payload_hash(source_payload)
            existing = by_linkage_key.get((self._linkage_type_key(linkage_type_value), linkage_id))
            if existing is None:
                created += 1
                if not dry_run:
                    ProductFitment.objects.create(
                        product=product,
                        note=f"Auto_DB_Pro article_li {linkage_type_value}",
                        is_exact=False,
                        source=ProductFitment.SOURCE_AUTODB_PRO,
                        autodb_passanger_car_id=linkage_id,
                        linkage_type=linkage_type_value,
                        autodb_article_key=article_key,
                        supplier_id=supplier_id,
                        article_number=article_number,
                        source_payload=source_payload,
                        source_hash=source_hash,
                        is_stale=False,
                        stale_reason="",
                        quality_status=ProductFitment.QUALITY_STATUS_TRUSTED,
                        quality_reason="",
                        excluded_from_public_filtering=False,
                        manual_locked=False,
                    )
                continue

            if existing.manual_locked:
                skipped_manual_locked = True
                continue

            changed = False
            if existing.is_stale:
                existing.is_stale = False
                changed = True
            if existing.stale_reason:
                existing.stale_reason = ""
                changed = True
            if str(existing.linkage_type or "") != linkage_type_value:
                existing.linkage_type = linkage_type_value
                changed = True
            if str(existing.autodb_article_key or "") != article_key:
                existing.autodb_article_key = article_key
                changed = True
            if self._safe_int(existing.supplier_id) != supplier_id:
                existing.supplier_id = supplier_id
                changed = True
            if str(existing.article_number or "") != article_number:
                existing.article_number = article_number
                changed = True
            if existing.source_payload != source_payload:
                existing.source_payload = source_payload
                changed = True
            if str(existing.source_hash or "") != source_hash:
                existing.source_hash = source_hash
                changed = True
            if existing.source != ProductFitment.SOURCE_AUTODB_PRO:
                existing.source = ProductFitment.SOURCE_AUTODB_PRO
                changed = True
            if str(existing.quality_status or "") != ProductFitment.QUALITY_STATUS_TRUSTED:
                existing.quality_status = ProductFitment.QUALITY_STATUS_TRUSTED
                changed = True
            if str(existing.quality_reason or ""):
                existing.quality_reason = ""
                changed = True
            if bool(existing.excluded_from_public_filtering):
                existing.excluded_from_public_filtering = False
                changed = True

            if changed:
                updated += 1
                if not dry_run:
                    existing.save(
                        update_fields=(
                            "source",
                            "linkage_type",
                            "autodb_article_key",
                            "supplier_id",
                            "article_number",
                            "source_payload",
                            "source_hash",
                            "is_stale",
                            "stale_reason",
                            "quality_status",
                            "quality_reason",
                            "excluded_from_public_filtering",
                            "updated_at",
                        )
                    )

        stale_marked = self._mark_missing_as_stale(
            product=product,
            active_linkage_keys=active_linkage_keys,
            dry_run=dry_run,
        )

        status = "updated" if (created + updated + stale_marked) > 0 else "skipped_hash_unchanged"
        if skipped_manual_locked and status == "skipped_hash_unchanged":
            status = "skipped_manual_locked"

        return ProductFitmentEnrichmentResult(
            product_id=str(product.id),
            status=status,
            has_fitments=bool(active_linkage_keys),
            fitments_created=created,
            fitments_updated=updated,
            stale_marked=stale_marked,
            skipped_no_autodb_link=False,
            skipped_no_article_li=False,
            skipped_non_passenger_car=False,
            skipped_missing_passanger_car=False,
            skipped_manual_locked=skipped_manual_locked,
        )

    def build_diagnostics(self, *, product: Product) -> ProductFitmentDiagnostics:
        supplier_id = self._safe_int(getattr(product, "autodb_supplier_id", None))
        article_number = str(getattr(product, "autodb_article_number", "") or "").strip()
        article_key = str(getattr(product, "autodb_article_key", "") or "").strip()

        article_rows: list[dict[str, Any]] = []
        passenger_rows: list[dict[str, Any]] = []
        passenger_ids: set[int] = set()
        passanger_car_rows: list[dict[str, Any]] = []
        proposed_creates: list[dict[str, Any]] = []
        proposed_updates: list[dict[str, Any]] = []
        proposed_stale: list[dict[str, Any]] = []
        skipped_reason = ""

        if supplier_id is None or not article_number:
            skipped_reason = "skipped_no_autodb_link"
        else:
            article_rows = self._find_article_li_rows(supplier_id=supplier_id, article_number=article_number)
            if not article_rows:
                skipped_reason = "skipped_no_article_li"
            else:
                linkage_rows: list[tuple[str, int]] = []
                for row in article_rows:
                    linkage_id = self._safe_int(find_value(row, ["linkageId", "linkageid", "LinkageId"]))
                    if linkage_id is None or linkage_id <= 0:
                        continue
                    linkage_type = self._normalize_linkage_type(find_value(row, ["linkageTypeId", "linkagetypeid", "LinkageTypeId"]))
                    linkage_rows.append((linkage_type, linkage_id))
                    if self._is_passenger_linkage(linkage_type):
                        passenger_rows.append(row)
                        passenger_ids.add(linkage_id)

                if not linkage_rows:
                    skipped_reason = "skipped_non_passenger_car"
                else:
                    passanger_car_rows = self._find_passanger_car_rows(linkage_ids=passenger_ids)
                    existing_passenger_ids = {self._safe_int(row.get("id")) for row in passanger_car_rows}
                    existing_passenger_ids.discard(None)

                    active_linkage_keys: set[tuple[str, int]] = set()
                    for linkage_type, linkage_id in linkage_rows:
                        if self._is_passenger_linkage(linkage_type) and linkage_id not in existing_passenger_ids:
                            continue
                        active_linkage_keys.add((self._linkage_type_key(linkage_type), linkage_id))

                    if not active_linkage_keys:
                        skipped_reason = "skipped_missing_passanger_car"

                    existing_fitments = list(
                        ProductFitment.objects.filter(
                            product=product,
                            source=ProductFitment.SOURCE_AUTODB_PRO,
                        ).order_by("id")
                    )
                    by_linkage_key = {
                        (self._linkage_type_key(item.linkage_type), int(item.autodb_passanger_car_id)): item
                        for item in existing_fitments
                        if item.autodb_passanger_car_id is not None
                    }

                    for linkage_type_key, linkage_id in sorted(active_linkage_keys, key=lambda item: (item[0], item[1])):
                        current = by_linkage_key.get((linkage_type_key, linkage_id))
                        if current is None:
                            proposed_creates.append(
                                {
                                    "source": ProductFitment.SOURCE_AUTODB_PRO,
                                    "linkage_type": linkage_type_key or self.LINKAGE_TYPE_PASSENGER_CAR,
                                    "autodb_passanger_car_id": linkage_id,
                                }
                            )
                        else:
                            proposed_updates.append(
                                {
                                    "id": str(current.id),
                                    "manual_locked": bool(current.manual_locked),
                                    "is_stale": bool(current.is_stale),
                                }
                            )

                    for row in existing_fitments:
                        linkage_id = self._safe_int(row.autodb_passanger_car_id)
                        if linkage_id is None:
                            continue
                        linkage_key = (self._linkage_type_key(row.linkage_type), linkage_id)
                        if linkage_key in active_linkage_keys:
                            continue
                        proposed_stale.append(
                            {
                                "id": str(row.id),
                                "autodb_passanger_car_id": linkage_id,
                                "manual_locked": bool(row.manual_locked),
                            }
                        )

        current_fitments = list(
            ProductFitment.objects.filter(product=product)
            .order_by("created_at", "id")
        )

        return ProductFitmentDiagnostics(
            product_id=str(product.id),
            bridge_supplier_id=supplier_id,
            bridge_article_number=article_number,
            bridge_article_key=article_key,
            article_li_rows=tuple(dict(row) for row in article_rows),
            passenger_candidates=tuple(
                {
                    "linkageTypeId": find_value(row, ["linkageTypeId", "linkagetypeid", "LinkageTypeId"]),
                    "linkageId": find_value(row, ["linkageId", "linkageid", "LinkageId"]),
                    "supplierId": find_value(row, ["supplierId", "supplierid", "SupplierId"]),
                    "DataSupplierArticleNumber": find_value(
                        row,
                        ["DataSupplierArticleNumber", "datasupplierarticlenumber", "dataSupplierArticleNumber"],
                    ),
                }
                for row in passenger_rows
            ),
            passanger_cars_rows=tuple(dict(row) for row in passanger_car_rows),
            current_fitments=tuple(self._serialize_fitment_row(item) for item in current_fitments),
            proposed_creates=tuple(proposed_creates),
            proposed_updates=tuple(proposed_updates),
            proposed_stale=tuple(proposed_stale),
            skipped_reason=skipped_reason,
        )

    def _find_article_li_rows(self, *, supplier_id: int, article_number: str) -> list[dict[str, Any]]:
        if supplier_id <= 0 or not article_number:
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

    def _find_existing_passanger_car_ids(self, *, linkage_ids: set[int]) -> set[int]:
        rows = self._find_passanger_car_rows(linkage_ids=linkage_ids)
        out: set[int] = set()
        for row in rows:
            value = self._safe_int(row.get("id"))
            if value is not None:
                out.add(value)
        return out

    def _find_passanger_car_rows(self, *, linkage_ids: set[int]) -> list[dict[str, Any]]:
        if not linkage_ids:
            return []
        self.storage.ensure_table("passanger_cars")
        columns = list(self.storage.get_local_columns("passanger_cars"))
        if not columns:
            return []

        id_column = find_column_name(columns, ["id", "ID"])
        if not id_column:
            return []

        return self.storage.fetch_local_rows_in(
            table="passanger_cars",
            column=id_column,
            values=sorted(linkage_ids),
            limit=max(len(linkage_ids) * 2, 100),
            columns=columns,
        )

    def _mark_missing_as_stale(self, *, product: Product, active_linkage_keys: set[tuple[str, int]], dry_run: bool) -> int:
        stale_marked = 0
        fitments = ProductFitment.objects.filter(
            product=product,
            source=ProductFitment.SOURCE_AUTODB_PRO,
        )
        for fitment in fitments.iterator(chunk_size=200):
            linkage_id = self._safe_int(fitment.autodb_passanger_car_id)
            linkage_key = (self._linkage_type_key(fitment.linkage_type), linkage_id) if linkage_id is not None else None
            if linkage_key is not None and linkage_key in active_linkage_keys:
                continue
            if fitment.manual_locked:
                continue
            stale_marked += 1
            if not dry_run and (not fitment.is_stale or fitment.stale_reason != "missing_from_latest_import"):
                fitment.is_stale = True
                fitment.stale_reason = "missing_from_latest_import"
                fitment.save(update_fields=("is_stale", "stale_reason", "updated_at"))
        return stale_marked

    def _normalize_linkage_type(self, value: Any) -> str:
        return str(value or "").strip() or self.LINKAGE_TYPE_PASSENGER_CAR

    def _linkage_type_key(self, value: Any) -> str:
        return str(value or "").strip().casefold()

    def _is_passenger_linkage(self, linkage_type: str) -> bool:
        return self._linkage_type_key(linkage_type) == self._linkage_type_key(self.LINKAGE_TYPE_PASSENGER_CAR)

    def _serialize_fitment_row(self, fitment: ProductFitment) -> dict[str, Any]:
        return {
            "id": str(fitment.id),
            "source": str(fitment.source or ""),
            "modification_id": "",
            "autodb_passanger_car_id": self._safe_int(fitment.autodb_passanger_car_id),
            "linkage_type": str(fitment.linkage_type or ""),
            "autodb_article_key": str(fitment.autodb_article_key or ""),
            "supplier_id": self._safe_int(fitment.supplier_id),
            "article_number": str(fitment.article_number or ""),
            "manual_locked": bool(fitment.manual_locked),
            "is_stale": bool(fitment.is_stale),
            "stale_reason": str(fitment.stale_reason or ""),
            "note": str(fitment.note or ""),
            "is_exact": bool(fitment.is_exact),
            "make": "",
            "model": "",
            "generation": "",
            "engine": "",
            "modification": "",
        }

    def _trim_article_li_row(self, row: dict[str, Any]) -> dict[str, Any]:
        keys = [
            "supplierId",
            "supplierid",
            "SupplierId",
            "DataSupplierArticleNumber",
            "datasupplierarticlenumber",
            "linkageTypeId",
            "linkagetypeid",
            "linkageId",
            "linkageid",
            "ProductId",
            "productid",
            "id",
        ]
        out: dict[str, Any] = {}
        for key in keys:
            value = find_value(row, [key])
            if value is None or str(value).strip() == "":
                continue
            out[key] = str(value)[:255]
        return out

    def _payload_hash(self, payload: dict[str, Any]) -> str:
        return sha1(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()  # noqa: S324

    def _safe_int(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
