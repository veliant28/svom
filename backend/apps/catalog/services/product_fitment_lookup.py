from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from django.conf import settings
from django.db.models import Case, IntegerField, OuterRef, Q, Subquery, Value, When

from apps.autocatalog.models import CarModification, UtrArticleDetailMap, UtrDetailCarMap
from apps.autodb.models import AutoDbArticleLinkage, AutoDbPassengerCar, AutoDbSupplier
from apps.catalog.models import Product
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand
from apps.users.models import GarageVehicle

FITMENT_PROVIDER_UTR = "utr"
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
    provider = str(getattr(settings, "FITMENT_PROVIDER", FITMENT_PROVIDER_AUTODB) or "").strip().lower()
    if provider == FITMENT_PROVIDER_AUTODB:
        return FITMENT_PROVIDER_AUTODB
    return FITMENT_PROVIDER_UTR


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


def resolve_selected_car_modification_id(request) -> int | None:
    if request is None:
        return None

    explicit_car_modification_id = parse_positive_int(request.query_params.get("car_modification"))
    if explicit_car_modification_id:
        return explicit_car_modification_id

    garage_vehicle_id = str(request.query_params.get("garage_vehicle") or "").strip()
    if not garage_vehicle_id:
        return None

    garage_vehicle = GarageVehicle.objects.filter(id=garage_vehicle_id).values("car_modification_id").first()
    return parse_positive_int(garage_vehicle.get("car_modification_id")) if garage_vehicle else None


def resolve_selected_autocatalog_vehicle(request) -> SelectedAutocatalogVehicle | None:
    car_modification_id = resolve_selected_car_modification_id(request)
    if not car_modification_id:
        return None

    row = (
        CarModification.objects.filter(id=car_modification_id)
        .select_related("make", "model")
        .values("id", "make_id", "make__name", "model_id", "model__name", "year")
        .first()
    )
    if not row:
        return None

    return SelectedAutocatalogVehicle(
        id=int(row["id"]),
        make_id=int(row["make_id"]),
        make_name=str(row["make__name"]),
        model_id=int(row["model_id"]),
        model_name=str(row["model__name"]),
        year=parse_positive_int(row.get("year")),
    )


def resolve_product_utr_detail_ids(*, product: Product) -> set[str]:
    detail_ids: set[str] = set()
    product_detail_id = str(product.utr_detail_id or "").strip()
    if product_detail_id:
        detail_ids.add(product_detail_id)

    mapped_detail_ids_qs = (
        SupplierRawOffer.objects.filter(
            matched_product_id=product.id,
            supplier__code="utr",
        )
        .annotate(
            map_detail_id=Subquery(
                UtrArticleDetailMap.objects.filter(
                    normalized_article=OuterRef("normalized_article"),
                    normalized_brand=OuterRef("normalized_brand"),
                )
                .exclude(utr_detail_id="")
                .values("utr_detail_id")[:1]
            )
        )
        .exclude(map_detail_id__isnull=True)
        .values_list("map_detail_id", flat=True)
        .distinct()
    )
    for detail_id in mapped_detail_ids_qs:
        normalized = str(detail_id or "").strip()
        if normalized:
            detail_ids.add(normalized)
    return detail_ids


def build_autocatalog_generation(car) -> str:
    if car.start_date_at or car.end_date_at:
        start_label = str(car.start_date_at.year) if car.start_date_at else "?"
        end_label = str(car.end_date_at.year) if car.end_date_at else "..."
        return f"{start_label}-{end_label}"
    if car.year:
        return str(car.year)
    return ""


def serialize_utr_fitment_mapping(mapping: UtrDetailCarMap) -> dict:
    car = mapping.car_modification
    return {
        "id": f"utr-{mapping.utr_detail_id}-{car.id}",
        "make": str(car.make.name),
        "model": str(car.model.name),
        "generation": build_autocatalog_generation(car),
        "engine": str(car.engine or ""),
        "modification": str(car.modification or ""),
        "note": "UTR applicability",
        "is_exact": False,
    }


def get_utr_fitment_queryset(*, detail_ids: set[str], selected_vehicle: SelectedAutocatalogVehicle | None = None):
    queryset = UtrDetailCarMap.objects.filter(utr_detail_id__in=sorted(detail_ids)).select_related(
        "car_modification",
        "car_modification__make",
        "car_modification__model",
    )

    if selected_vehicle is not None:
        queryset = queryset.annotate(
            selected_order=Case(
                When(car_modification_id=selected_vehicle.id, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            ),
            selected_model_order=Case(
                When(
                    car_modification__make_id=selected_vehicle.make_id,
                    car_modification__model_id=selected_vehicle.model_id,
                    then=Value(0),
                ),
                default=Value(1),
                output_field=IntegerField(),
            ),
        ).order_by(
            "selected_order",
            "selected_model_order",
            "utr_detail_id",
            "car_modification__make__name",
            "car_modification__model__name",
            "car_modification__year",
            "car_modification__modification",
            "car_modification__engine",
            "car_modification_id",
        )
    else:
        queryset = queryset.order_by(
            "utr_detail_id",
            "car_modification__make__name",
            "car_modification__model__name",
            "car_modification__year",
            "car_modification__modification",
            "car_modification__engine",
            "car_modification_id",
        )

    return queryset


def build_autodb_generation(car: AutoDbPassengerCar) -> str:
    if car.start_year or car.end_year:
        start_label = str(car.start_year) if car.start_year else "?"
        end_label = str(car.end_year) if car.end_year else "..."
        return f"{start_label}-{end_label}"
    return str(car.construction_interval or "").strip()


def serialize_autodb_fitment_mapping(car: AutoDbPassengerCar) -> dict:
    model = car.model
    manufacturer = model.manufacturer if model is not None else None
    return {
        "id": f"autodb-{car.id}",
        "make": str(manufacturer.description if manufacturer is not None else ""),
        "model": str(model.description if model is not None else ""),
        "generation": build_autodb_generation(car),
        "engine": "",
        "modification": str(car.full_description or car.description or ""),
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


def _annotate_autodb_selected_vehicle_order(
    *,
    queryset,
    selected_vehicle: SelectedAutocatalogVehicle | None,
):
    if selected_vehicle is None:
        return queryset.order_by(
            "model__manufacturer__description",
            "model__description",
            "start_year",
            "end_year",
            "id",
        )

    make_signature = _normalized_signature(selected_vehicle.make_name)
    model_signature = _normalized_signature(selected_vehicle.model_name)

    # Prefer direct exact-name match if names are aligned between autocatalog and Auto-DB.
    queryset = queryset.annotate(
        selected_make_order=Case(
            When(model__manufacturer__description=selected_vehicle.make_name, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        ),
        selected_model_order=Case(
            When(
                model__manufacturer__description=selected_vehicle.make_name,
                model__description=selected_vehicle.model_name,
                then=Value(0),
            ),
            default=Value(1),
            output_field=IntegerField(),
        ),
    )

    if make_signature or model_signature:
        # Secondary order to keep likely matches close to top when exact text differs slightly.
        queryset = queryset.annotate(
            selected_signature_order=Case(
                When(
                    model__manufacturer__matchcode__iexact=make_signature,
                    then=Value(0),
                ),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        return queryset.order_by(
            "selected_model_order",
            "selected_make_order",
            "selected_signature_order",
            "model__manufacturer__description",
            "model__description",
            "start_year",
            "end_year",
            "id",
        )

    return queryset.order_by(
        "selected_model_order",
        "selected_make_order",
        "model__manufacturer__description",
        "model__description",
        "start_year",
        "end_year",
        "id",
    )


def get_autodb_fitment_queryset(*, product: Product, selected_vehicle: SelectedAutocatalogVehicle | None = None):
    pairs = _resolve_product_autodb_article_brand_pairs(product=product)
    if not pairs:
        return AutoDbPassengerCar.objects.none()

    normalized_brands = {brand for _, brand in pairs}
    supplier_ids = _resolve_autodb_supplier_ids_by_brands(normalized_brands=normalized_brands)
    if not supplier_ids:
        return AutoDbPassengerCar.objects.none()

    articles = {article for article, _ in pairs}
    linkage_ids = AutoDbArticleLinkage.objects.filter(
        supplier_id__in=sorted(supplier_ids),
        normalized_article__in=sorted(articles),
    ).values_list("linkage_id", flat=True)

    queryset = AutoDbPassengerCar.objects.filter(id__in=Subquery(linkage_ids)).select_related(
        "model",
        "model__manufacturer",
    )
    return _annotate_autodb_selected_vehicle_order(queryset=queryset, selected_vehicle=selected_vehicle)


def _resolve_selected_vehicle_by_car_modification_id(*, car_modification_id: int) -> SelectedAutocatalogVehicle | None:
    row = (
        CarModification.objects.filter(id=car_modification_id)
        .select_related("make", "model")
        .values("id", "make_id", "make__name", "model_id", "model__name", "year")
        .first()
    )
    if not row:
        return None
    return SelectedAutocatalogVehicle(
        id=int(row["id"]),
        make_id=int(row["make_id"]),
        make_name=str(row["make__name"]),
        model_id=int(row["model_id"]),
        model_name=str(row["model__name"]),
        year=parse_positive_int(row.get("year")),
    )


def resolve_autodb_matched_product_ids_for_car_modification(*, car_modification_id: int) -> set[str]:
    selected_vehicle = _resolve_selected_vehicle_by_car_modification_id(car_modification_id=car_modification_id)
    if selected_vehicle is None:
        return set()
    return resolve_autodb_matched_product_ids_for_selected_vehicle(selected_vehicle=selected_vehicle)


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

    make_token = make_name.split()[0]
    model_token = model_name.split()[0]
    cars = AutoDbPassengerCar.objects.select_related("model", "model__manufacturer").filter(
        model__manufacturer__description__icontains=make_token,
        model__description__icontains=model_token,
    )
    selected_year = parse_positive_int(selected_vehicle.year)
    if selected_year:
        cars = cars.filter(
            Q(start_year__isnull=True) | Q(start_year__lte=selected_year),
            Q(end_year__isnull=True) | Q(end_year__gte=selected_year),
        )

    car_ids = list(cars.values_list("id", flat=True))
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
