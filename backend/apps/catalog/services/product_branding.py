from __future__ import annotations

from dataclasses import dataclass

from apps.catalog.models import Product
from apps.catalog.services.brand_management import sanitize_brand_name


@dataclass(frozen=True)
class ProductBrandDisplay:
    display_brand: str
    brand_source: str
    autodb_supplier_name: str
    current_brand_name: str


def get_product_display_brand_payload(product: Product) -> ProductBrandDisplay:
    linked = bool(getattr(product, "autodb_supplier_id", None))

    autodb_supplier_name = sanitize_brand_name(str(getattr(product, "autodb_supplier_name", "") or ""))
    display_brand_name = sanitize_brand_name(str(getattr(product, "display_brand_name", "") or ""))
    normalized_brand = sanitize_brand_name(str(getattr(product, "normalized_brand", "") or ""))
    current_brand_name = display_brand_name or autodb_supplier_name or normalized_brand
    source = str(getattr(product, "brand_source", "") or "").strip()

    if linked and autodb_supplier_name:
        return ProductBrandDisplay(
            display_brand=autodb_supplier_name,
            brand_source=Product.BRAND_SOURCE_AUTODB_PRO,
            autodb_supplier_name=autodb_supplier_name,
            current_brand_name=current_brand_name,
        )

    if display_brand_name:
        resolved_source = source or (Product.BRAND_SOURCE_AUTODB_PRO if linked else Product.BRAND_SOURCE_SUPPLIER_FALLBACK)
        return ProductBrandDisplay(
            display_brand=display_brand_name,
            brand_source=resolved_source,
            autodb_supplier_name=autodb_supplier_name,
            current_brand_name=current_brand_name,
        )

    if not linked:
        fallback_brand = normalized_brand or current_brand_name
        if fallback_brand:
            return ProductBrandDisplay(
                display_brand=fallback_brand,
                brand_source=Product.BRAND_SOURCE_SUPPLIER_FALLBACK,
                autodb_supplier_name=autodb_supplier_name,
                current_brand_name=current_brand_name,
            )

    return ProductBrandDisplay(
        display_brand="",
        brand_source=Product.BRAND_SOURCE_UNKNOWN,
        autodb_supplier_name=autodb_supplier_name,
        current_brand_name=current_brand_name,
    )


def get_product_display_brand(product: Product) -> str:
    return get_product_display_brand_payload(product).display_brand
