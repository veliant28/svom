from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from django.db.models import Q

from apps.autodb.models import AutoDbArticleLinkage, AutoDbSupplier
from apps.autodb.selectors import list_passanger_cars, list_passanger_cars_by_ids, list_vehicle_manufacturers, list_vehicle_models
from apps.catalog.models import AutoDbProductLinkQuality, Product
from apps.catalog.services.autodb_vehicle_display import (
    build_autodb_garage_vehicle_label,
    build_autodb_passanger_car_label,
)
from apps.compatibility.models import ProductFitment
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand
from apps.users.models import GarageVehicle

FITMENT_PROVIDER_AUTODB = "autodb"


@dataclass(frozen=True)
class SelectedAutocatalogVehicle:
    id: int
    make_id: int
    make_name: str
    model_id: int
    model_name: str
    year: int | None


def get_fitment_provider() -> str:
    # Catalog runtime policy: compatibility/filtering is Auto_DB-only.
    # UTR remains a price supplier and must not be used as compatibility provider.
    return FITMENT_PROVIDER_AUTODB


def is_autodb_fitment_provider() -> bool:
    return get_fitment_provider() == FITMENT_PROVIDER_AUTODB


def parse_positive_int(value) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def resolve_selected_autocatalog_vehicle(request) -> SelectedAutocatalogVehicle | None:
    selected_passanger_car_id = resolve_selected_passanger_car_id(request)
    if selected_passanger_car_id:
        row = list_passanger_cars_by_ids([selected_passanger_car_id]).get(int(selected_passanger_car_id))
        if row is not None:
            year_from = parse_positive_int(row.get("year_from")) or parse_positive_int(str(row.get("years") or "").split("–")[0] if row.get("years") else None)
            return SelectedAutocatalogVehicle(
                id=int(row.get("vehicle_id") or selected_passanger_car_id),
                make_id=int(row.get("manufacturer_id") or 0),
                make_name=str(row.get("make") or ""),
                model_id=int(row.get("model_id") or 0),
                model_name=str(row.get("model") or ""),
                year=year_from,
            )
    return None


def _resolve_selected_garage_vehicle(*, request, passanger_car_id: int | None):
    if request is None:
        return None

    garage_vehicle_id = str(request.query_params.get("garage_vehicle") or "").strip()
    if garage_vehicle_id:
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return None
        row = (
            GarageVehicle.objects.filter(
                id=garage_vehicle_id,
                user=user,
                catalog_source=GarageVehicle.CATALOG_SOURCE_AUTODB_PRO,
            )
            .select_related("make", "model")
            .first()
        )
        if row and (
            passanger_car_id is None
            or parse_positive_int(row.autodb_passanger_car_id) == passanger_car_id
        ):
            return row

    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False) or not passanger_car_id:
        return None

    return (
        GarageVehicle.objects.filter(
            user=user,
            catalog_source=GarageVehicle.CATALOG_SOURCE_AUTODB_PRO,
            autodb_passanger_car_id=passanger_car_id,
        )
        .select_related("make", "model")
        .order_by("-is_primary", "-updated_at", "-created_at")
        .first()
    )


def resolve_selected_autodb_vehicle_display(request) -> dict[str, str | int] | None:
    passanger_car_id = resolve_selected_passanger_car_id(request)
    if not passanger_car_id:
        return None

    selector_payload = list_passanger_cars_by_ids([passanger_car_id]).get(int(passanger_car_id))
    if selector_payload is not None:
        return selector_payload

    garage_vehicle = _resolve_selected_garage_vehicle(request=request, passanger_car_id=passanger_car_id)
    if garage_vehicle is not None:
        return build_autodb_garage_vehicle_label(
            garage_vehicle=garage_vehicle,
            passanger_car_id=passanger_car_id,
        )

    return {
        "vehicle_id": int(passanger_car_id),
        "make": "",
        "model": "",
        "modification": "",
        "years": "",
        "engine": "",
        "body": "",
        "label": f"Автомобиль #{passanger_car_id}",
        "subtitle": "",
    }


def resolve_selected_passanger_car_id(request) -> int | None:
    if request is None:
        return None

    for key in ("passanger_car_id", "vehicle_id"):
        parsed = parse_positive_int(request.query_params.get(key))
        if parsed:
            return parsed

    garage_vehicle_id = str(request.query_params.get("garage_vehicle") or "").strip()
    if not garage_vehicle_id:
        return None

    row = (
        GarageVehicle.objects.filter(id=garage_vehicle_id)
        .values("catalog_source", "autodb_passanger_car_id")
        .first()
    )
    if not row:
        return None
    if str(row.get("catalog_source") or "").strip() != GarageVehicle.CATALOG_SOURCE_AUTODB_PRO:
        return None
    return parse_positive_int(row.get("autodb_passanger_car_id"))


def serialize_autodb_fitment_mapping(car: dict[str, object]) -> dict:
    label = build_autodb_passanger_car_label(car)
    vehicle_id = int(label.get("vehicle_id") or car.get("vehicle_id") or 0)
    return {
        "id": f"autodb-{vehicle_id}",
        "vehicle_id": vehicle_id,
        "make": str(label.get("make") or ""),
        "model": str(label.get("model") or ""),
        "generation": str(label.get("years") or ""),
        "engine": str(label.get("engine") or ""),
        "modification": str(label.get("modification") or label.get("label") or ""),
        "body": str(label.get("body") or ""),
        "label": str(label.get("label") or ""),
        "subtitle": str(label.get("subtitle") or ""),
        "model_id": int(car.get("model_id") or 0),
        "manufacturer_id": int(car.get("manufacturer_id") or 0),
        "note": "Auto-DB Pro applicability",
        "is_exact": False,
    }


def serialize_autodb_fitment_mapping_from_selector(vehicle: dict[str, object]) -> dict:
    vehicle_id = int(vehicle.get("vehicle_id") or 0)
    label = str(vehicle.get("label") or "").strip() or (f"Автомобиль #{vehicle_id}" if vehicle_id else "Автомобиль")
    return {
        "id": f"autodb-{vehicle_id}",
        "vehicle_id": vehicle_id,
        "make": str(vehicle.get("make") or ""),
        "model": str(vehicle.get("model") or ""),
        "generation": str(vehicle.get("years") or ""),
        "engine": str(vehicle.get("engine") or ""),
        "modification": str(vehicle.get("modification") or label),
        "body": str(vehicle.get("body") or ""),
        "label": label,
        "subtitle": str(vehicle.get("subtitle") or ""),
        "model_id": int(vehicle.get("model_id") or 0),
        "manufacturer_id": int(vehicle.get("manufacturer_id") or 0),
        "note": "Auto-DB Pro applicability",
        "is_exact": False,
    }


def serialize_autodb_fitment_fallback_row(*, passanger_car_id: int, selected_vehicle: dict[str, str | int] | None = None) -> dict:
    selected_id = int(selected_vehicle.get("vehicle_id", 0)) if selected_vehicle else 0
    if selected_vehicle and selected_id == int(passanger_car_id):
        label = str(selected_vehicle.get("label") or "")
        return {
            "id": f"autodb-{passanger_car_id}",
            "vehicle_id": int(passanger_car_id),
            "make": str(selected_vehicle.get("make") or ""),
            "model": str(selected_vehicle.get("model") or ""),
            "generation": str(selected_vehicle.get("years") or ""),
            "engine": str(selected_vehicle.get("engine") or ""),
            "modification": str(selected_vehicle.get("modification") or label),
            "body": str(selected_vehicle.get("body") or ""),
            "label": label or f"Автомобиль #{passanger_car_id}",
            "subtitle": str(selected_vehicle.get("subtitle") or ""),
            "note": "Auto-DB Pro applicability",
            "is_exact": False,
        }

    return {
        "id": f"autodb-{passanger_car_id}",
        "vehicle_id": int(passanger_car_id),
        "make": "",
        "model": "",
        "generation": "",
        "engine": "",
        "modification": "",
        "body": "",
        "label": f"Автомобиль #{passanger_car_id}",
        "subtitle": "",
        "note": "Auto-DB Pro applicability",
        "is_exact": False,
    }


def _resolve_product_autodb_article_brand_pairs(*, product: Product) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    fallback_brand = normalize_brand(getattr(product.brand, "name", ""))

    product_article = normalize_article(product.article)
    if product_article and fallback_brand:
        pairs.add((product_article, fallback_brand))

    raw_offers = (
        SupplierRawOffer.objects.filter(matched_product_id=product.id)
        .exclude(normalized_article="")
        .values_list("normalized_article", "normalized_brand")
        .distinct()
    )
    for article, brand in raw_offers:
        normalized_article = str(article or "").strip()
        if not normalized_article:
            continue
        normalized_brand = str(brand or "").strip() or fallback_brand
        if not normalized_brand:
            continue
        pairs.add((normalized_article, normalized_brand))
    return pairs


def _resolve_autodb_supplier_ids_by_brands(*, normalized_brands: set[str]) -> set[int]:
    brands = {str(value or "").strip() for value in normalized_brands if str(value or "").strip()}
    if not brands:
        return set()
    supplier_rows = AutoDbSupplier.objects.filter(
        Q(normalized_matchcode__in=sorted(brands)) | Q(normalized_name__in=sorted(brands))
    ).values_list("id", flat=True)
    return {int(value) for value in supplier_rows}


def _normalized_signature(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def get_autodb_fitment_queryset(*, product: Product, selected_vehicle: SelectedAutocatalogVehicle | None = None):
    if not _can_use_autodb_fitments_for_public(product=product):
        return []
    fitment_ids = get_public_autodb_fitment_ids(product=product)
    vehicle_map = resolve_public_autodb_vehicle_map(passanger_car_ids=fitment_ids)
    rows: list[dict[str, object]] = []
    for car_id in sorted(set(fitment_ids)):
        vehicle = vehicle_map.get(int(car_id))
        if vehicle is not None:
            rows.append(dict(vehicle))
            continue
        rows.append(
            {
                "vehicle_id": int(car_id),
                "model_id": 0,
                "manufacturer_id": 0,
                "make": "",
                "model": "",
                "modification": "",
                "years": "",
                "engine": "",
                "body": "",
                "label": f"Автомобиль #{int(car_id)}",
                "subtitle": "",
            }
        )
    if selected_vehicle is None:
        return rows
    selected_make = _normalized_signature(selected_vehicle.make_name)
    selected_model = _normalized_signature(selected_vehicle.model_name)

    def _order(row: dict[str, object]) -> tuple[int, int, str, str, int]:
        make = _normalized_signature(str(row.get("make") or ""))
        model = _normalized_signature(str(row.get("model") or ""))
        model_match = 0 if (selected_make and selected_model and make == selected_make and model == selected_model) else 1
        make_match = 0 if (selected_make and make == selected_make) else 1
        return (
            model_match,
            make_match,
            str(row.get("make") or ""),
            str(row.get("model") or ""),
            int(row.get("vehicle_id") or 0),
        )

    return sorted(rows, key=_order)


def get_public_autodb_fitment_ids(*, product: Product) -> list[int]:
    if not _can_use_autodb_fitments_for_public(product=product):
        return []
    rows = (
        ProductFitment.objects.filter(
            product=product,
            source=ProductFitment.SOURCE_AUTODB_PRO,
            is_stale=False,
            excluded_from_public_filtering=False,
            quality_status=ProductFitment.QUALITY_STATUS_TRUSTED,
        )
        .exclude(autodb_passanger_car_id__isnull=True)
        .values_list("autodb_passanger_car_id", flat=True)
        .distinct()
    )
    return [int(value) for value in rows if value]


def resolve_public_autodb_vehicle_map(*, passanger_car_ids: list[int]) -> dict[int, dict[str, object]]:
    if not passanger_car_ids:
        return {}
    return list_passanger_cars_by_ids(passanger_car_ids)


def _can_use_autodb_fitments_for_public(*, product: Product) -> bool:
    article_key = str(getattr(product, "autodb_article_key", "") or "").strip()
    if not article_key:
        return False
    has_trusted_quality = AutoDbProductLinkQuality.objects.filter(
        product=product,
        autodb_article_key=article_key,
        status=AutoDbProductLinkQuality.STATUS_TRUSTED,
    ).exists()
    if not has_trusted_quality:
        return False
    return ProductFitment.objects.filter(
        product=product,
        source=ProductFitment.SOURCE_AUTODB_PRO,
        autodb_article_key=article_key,
        is_stale=False,
        excluded_from_public_filtering=False,
        quality_status=ProductFitment.QUALITY_STATUS_TRUSTED,
        autodb_passanger_car_id__isnull=False,
    ).exists()


def resolve_autodb_matched_product_ids_for_selected_vehicle(
    *,
    selected_vehicle: SelectedAutocatalogVehicle | None,
) -> set[str]:
    if selected_vehicle is None:
        return set()

    make_name = str(selected_vehicle.make_name or "").strip()
    model_name = str(selected_vehicle.model_name or "").strip()
    if not make_name or not model_name:
        return set()

    make_token = _normalized_signature(make_name.split()[0])
    model_token = _normalized_signature(model_name.split()[0])
    selected_year = parse_positive_int(selected_vehicle.year)

    manufacturer_ids: set[int] = set()
    for manufacturer in list_vehicle_manufacturers():
        manufacturer_name = str(manufacturer.get("name") or "")
        manufacturer_sig = _normalized_signature(manufacturer_name)
        if make_token and make_token in manufacturer_sig:
            manufacturer_ids.add(int(manufacturer.get("id") or 0))
    manufacturer_ids.discard(0)
    if not manufacturer_ids:
        return set()

    model_ids: set[int] = set()
    for manufacturer_id in sorted(manufacturer_ids):
        for model in list_vehicle_models(manufacturer_id=manufacturer_id):
            model_name_value = str(model.get("name") or "")
            model_sig = _normalized_signature(model_name_value)
            if model_token and model_token in model_sig:
                model_ids.add(int(model.get("id") or 0))
    model_ids.discard(0)
    if not model_ids:
        return set()

    car_ids: list[int] = []
    for model_id in sorted(model_ids):
        for car in list_passanger_cars(model_id=model_id):
            car_id = parse_positive_int(car.get("id"))
            if not car_id:
                continue
            if selected_year:
                year_from = parse_positive_int(car.get("year_from"))
                year_to = parse_positive_int(car.get("year_to"))
                if year_from and selected_year < year_from:
                    continue
                if year_to and selected_year > year_to:
                    continue
            car_ids.append(car_id)
    if not car_ids:
        return set()

    linkages = list(
        AutoDbArticleLinkage.objects.filter(linkage_id__in=car_ids)
        .values_list("supplier_id", "normalized_article")
        .distinct()
    )
    if not linkages:
        return set()

    supplier_ids = sorted({int(supplier_id) for supplier_id, _ in linkages})
    supplier_rows = AutoDbSupplier.objects.filter(id__in=supplier_ids).values(
        "id",
        "normalized_matchcode",
        "normalized_name",
    )
    supplier_brand_signatures: dict[int, set[str]] = defaultdict(set)
    for row in supplier_rows:
        supplier_id = int(row["id"])
        normalized_matchcode = str(row.get("normalized_matchcode") or "").strip()
        normalized_name = str(row.get("normalized_name") or "").strip()
        if normalized_matchcode:
            supplier_brand_signatures[supplier_id].add(normalized_matchcode)
        if normalized_name:
            supplier_brand_signatures[supplier_id].add(normalized_name)

    article_to_brands: dict[str, set[str]] = defaultdict(set)
    for supplier_id, normalized_article in linkages:
        article = str(normalized_article or "").strip()
        if not article:
            continue
        brands = supplier_brand_signatures.get(int(supplier_id), set())
        for brand in brands:
            article_to_brands[article].add(brand)

    if not article_to_brands:
        return set()

    all_articles = sorted(article_to_brands.keys())
    all_brands = sorted({brand for brands in article_to_brands.values() for brand in brands})
    if not all_brands:
        return set()

    matched_ids: set[str] = set()
    offers = (
        SupplierRawOffer.objects.filter(
            matched_product_id__isnull=False,
            normalized_article__in=all_articles,
            normalized_brand__in=all_brands,
        )
        .values_list("matched_product_id", "normalized_article", "normalized_brand")
        .iterator(chunk_size=5000)
    )
    for product_id, normalized_article, normalized_brand in offers:
        article = str(normalized_article or "").strip()
        brand = str(normalized_brand or "").strip()
        if not article or not brand:
            continue
        if brand in article_to_brands.get(article, set()):
            matched_ids.add(str(product_id))
    return matched_ids
