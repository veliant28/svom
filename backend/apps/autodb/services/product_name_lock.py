from __future__ import annotations

from apps.catalog.models import Product


def is_product_name_manual_locked(product: Product) -> bool:
    return bool(getattr(product, "name_manually_locked", False)) or (
        str(getattr(product, "name_translation_status", "") or "") == Product.NAME_TRANSLATION_MANUAL_LOCKED
    )

