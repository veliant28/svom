from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime

from django.conf import settings
from django.core.cache import cache
from django.db import DataError, transaction
from django.utils.text import slugify

from apps.autocatalog.models import CarMake, CarModel, CarModification, UtrDetailCarMap
from apps.autocatalog.models.normalization import collapse_spaces, normalize_name
from apps.supplier_imports.services.integrations.exceptions import SupplierClientError
from apps.supplier_imports.services.integrations.utr_client import UtrClient

logger = logging.getLogger(__name__)


@dataclass
class AutocatalogImportSummary:
    detail_ids_total: int = 0
    detail_ids_processed: int = 0
    detail_ids_failed: int = 0
    detail_ids_skipped_cached: int = 0
    detail_ids_skipped_disabled: int = 0
    detail_ids_empty_applicability: int = 0
    stopped_due_to_circuit_breaker: int = 0
    makes_created: int = 0
    models_created: int = 0
    modifications_created: int = 0
    modifications_end_date_updated: int = 0
    mappings_created: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


class UtrAutocatalogImportService:
    def __init__(self, *, client: UtrClient | None = None):
        self.client = client or UtrClient()

    def import_from_detail_ids(
        self,
        *,
        detail_ids: list[str],
        access_token: str,
        on_error: callable | None = None,
        on_progress: callable | None = None,
        continue_on_error: bool = True,
        force_refresh: bool | None = None,
    ) -> AutocatalogImportSummary:
        effective_force_refresh = bool(getattr(settings, "UTR_FORCE_REFRESH", False)) if force_refresh is None else bool(force_refresh)
        applicability_enabled = bool(getattr(settings, "UTR_APPLICABILITY_ENABLED", True))

        normalized_detail_ids: list[str] = []
        seen_ids: set[str] = set()
        for detail_id in detail_ids:
            normalized_detail_id = self._normalize_detail_id(detail_id)
            if not normalized_detail_id or normalized_detail_id in seen_ids:
                continue
            seen_ids.add(normalized_detail_id)
            normalized_detail_ids.append(normalized_detail_id)

        summary = AutocatalogImportSummary(detail_ids_total=len(normalized_detail_ids))
        if not normalized_detail_ids:
            return summary

        persisted_with_mappings: set[str] = set()
        if not effective_force_refresh:
            persisted_with_mappings = set(
                UtrDetailCarMap.objects.filter(utr_detail_id__in=normalized_detail_ids)
                .values_list("utr_detail_id", flat=True)
                .distinct()
            )

        total = len(normalized_detail_ids)
        for index, normalized_detail_id in enumerate(normalized_detail_ids, start=1):
            if not applicability_enabled:
                summary.detail_ids_skipped_disabled += 1
                continue

            if not effective_force_refresh:
                if normalized_detail_id in persisted_with_mappings or self._is_detail_marked_done(normalized_detail_id):
                    summary.detail_ids_skipped_cached += 1
                    continue

            summary.detail_ids_processed += 1
            try:
                applicability_rows = self.client.fetch_applicability(
                    access_token=access_token,
                    detail_id=normalized_detail_id,
                    force_refresh=effective_force_refresh,
                    request_reason="autocatalog:detail_applicability_import",
                )
            except SupplierClientError as exc:
                summary.detail_ids_failed += 1
                if self.client.is_circuit_open_error(exc):
                    summary.stopped_due_to_circuit_breaker += 1
                    if on_error is not None:
                        on_error(normalized_detail_id, str(exc))
                    if not continue_on_error:
                        raise
                    break
                if on_error is not None:
                    on_error(normalized_detail_id, str(exc))
                if not continue_on_error:
                    raise
                continue

            if not applicability_rows:
                summary.detail_ids_empty_applicability += 1

            self._import_applicability_rows(
                detail_id=normalized_detail_id,
                applicability_rows=applicability_rows,
                summary=summary,
            )
            self._mark_detail_done(normalized_detail_id)
            if on_progress is not None:
                on_progress(index, total, normalized_detail_id)

        return summary

    @transaction.atomic
    def _import_applicability_rows(
        self,
        *,
        detail_id: str,
        applicability_rows: list[dict],
        summary: AutocatalogImportSummary,
    ) -> None:
        for manufacturer_row in applicability_rows:
            make_name = str(manufacturer_row.get("manufacturer", "")).strip()
            if not make_name:
                continue
            make, make_created = self._get_or_create_make(make_name)
            summary.makes_created += int(make_created)

            models = manufacturer_row.get("models") or []
            if not isinstance(models, list):
                continue

            for model_row in models:
                model_name = str((model_row or {}).get("model", "")).strip()
                if not model_name:
                    continue
                model, model_created = self._get_or_create_model(make=make, name=model_name)
                summary.models_created += int(model_created)

                cars = (model_row or {}).get("cars") or []
                if not isinstance(cars, list):
                    continue

                for car_row in cars:
                    if not isinstance(car_row, dict):
                        continue

                    modification_name, capacity, engine = self._prepare_modification_values(
                        detail_id=detail_id,
                        car_row=car_row,
                    )
                    start_date_at = self._parse_start_date(car_row.get("startDateAt"))
                    end_date_at = self._parse_end_date(car_row.get("endDateAt"))
                    hp_from = self._parse_optional_int(car_row.get("capacityHpFrom"))
                    kw_from = self._parse_optional_int(car_row.get("capacityKwFrom"))

                    dedupe_key = CarModification.build_dedupe_key(
                        make_id=make.id,
                        model_id=model.id,
                        start_date_at=start_date_at,
                        modification=modification_name,
                        capacity=capacity,
                        engine=engine,
                        hp_from=hp_from,
                        kw_from=kw_from,
                    )

                    try:
                        car_modification, modification_created = CarModification.objects.get_or_create(
                            dedupe_key=dedupe_key,
                            defaults={
                                "make": make,
                                "model": model,
                                "start_date_at": start_date_at,
                                "year": start_date_at.year if start_date_at else None,
                                "modification": modification_name,
                                "capacity": capacity,
                                "engine": engine,
                                "hp_from": hp_from,
                                "kw_from": kw_from,
                            },
                        )
                    except DataError as exc:
                        logger.exception(
                            "[UTR][applicability-import] DataError detail_id=%s make=%s model=%s error=%s",
                            detail_id,
                            make.name,
                            model.name,
                            exc,
                        )
                        raise
                    summary.modifications_created += int(modification_created)

                    # Business rule: use only UTR period end (endDateAt) to fill/update local end_date_at.
                    if end_date_at and car_modification.end_date_at != end_date_at:
                        car_modification.end_date_at = end_date_at
                        car_modification.save(update_fields=["end_date_at", "updated_at"])
                        summary.modifications_end_date_updated += 1

                    _, mapping_created = UtrDetailCarMap.objects.get_or_create(
                        utr_detail_id=detail_id,
                        car_modification=car_modification,
                    )
                    summary.mappings_created += int(mapping_created)

    def _get_or_create_make(self, name: str) -> tuple[CarMake, bool]:
        normalized_name = normalize_name(name)
        make = CarMake.objects.filter(normalized_name=normalized_name).first()
        if make:
            return make, False

        return CarMake.objects.get_or_create(
            normalized_name=normalized_name,
            defaults={
                "name": collapse_spaces(name),
                "slug": self._build_unique_make_slug(name),
            },
        )

    def _get_or_create_model(self, *, make: CarMake, name: str) -> tuple[CarModel, bool]:
        normalized_name = normalize_name(name)
        model = CarModel.objects.filter(make=make, normalized_name=normalized_name).first()
        if model:
            return model, False

        return CarModel.objects.get_or_create(
            make=make,
            normalized_name=normalized_name,
            defaults={
                "name": collapse_spaces(name),
                "slug": self._build_unique_model_slug(make=make, name=name),
            },
        )

    def _build_unique_make_slug(self, name: str) -> str:
        base = (slugify(name) or "make")[:132]
        slug = base
        suffix = 2
        while CarMake.objects.filter(slug=slug).exists():
            slug = f"{base}-{suffix}"[:140]
            suffix += 1
        return slug

    def _build_unique_model_slug(self, *, make: CarMake, name: str) -> str:
        base = (slugify(name) or "model")[:132]
        slug = base
        suffix = 2
        while CarModel.objects.filter(make=make, slug=slug).exists():
            slug = f"{base}-{suffix}"[:140]
            suffix += 1
        return slug

    def _normalize_detail_id(self, value) -> str:
        text = str(value or "").strip()
        if not text.isdigit():
            return ""
        return text

    def _parse_start_date(self, value) -> date | None:
        text = str(value or "").strip()
        if not text:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None

    def _parse_end_date(self, value) -> date | None:
        text = str(value or "").strip()
        if not text:
            return None
        lowered = text.lower()
        if lowered in {"-", "present", "current", "now", "null", "none"}:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None

    def _parse_optional_int(self, value) -> int | None:
        text = str(value or "").strip()
        if not text:
            return None
        if text.isdigit():
            return int(text)
        return None

    def _prepare_modification_values(self, *, detail_id: str, car_row: dict) -> tuple[str, str, str]:
        modification_name = collapse_spaces(str(car_row.get("car", "")).strip())
        capacity = collapse_spaces(str(car_row.get("capacity", "")).strip())
        engine = collapse_spaces(str(car_row.get("engine", "")).strip())

        values = {
            "modification": modification_name,
            "capacity": capacity,
            "engine": engine,
        }
        for field_name, value in values.items():
            field = CarModification._meta.get_field(field_name)
            max_length = int(getattr(field, "max_length", 0) or 0)
            if max_length and len(value) > max_length:
                logger.error(
                    "[UTR][applicability-import] overflow detail_id=%s field=%s value_length=%s max_length=%s",
                    detail_id,
                    field_name,
                    len(value),
                    max_length,
                )
                raise DataError(f"UTR {field_name} length overflow: {len(value)} > {max_length}")

        return modification_name, capacity, engine

    def _detail_done_cache_key(self, detail_id: str) -> str:
        return f"utr:autocatalog:applicability_done:{detail_id}"

    def _is_detail_marked_done(self, detail_id: str) -> bool:
        try:
            return bool(cache.get(self._detail_done_cache_key(detail_id)))
        except Exception:
            return False

    def _mark_detail_done(self, detail_id: str) -> None:
        ttl_seconds = max(int(getattr(settings, "UTR_CACHE_TTL_SECONDS", 60 * 60 * 24 * 30)), 60)
        try:
            cache.set(self._detail_done_cache_key(detail_id), 1, timeout=ttl_seconds)
        except Exception:
            return
