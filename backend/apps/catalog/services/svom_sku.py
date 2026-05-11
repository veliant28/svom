from __future__ import annotations

import hashlib
import re
from uuid import UUID

from apps.catalog.models import Product


SVOM_SKU_RE = re.compile(r"^\dS\dV\dO\dM\d{4}$")


def is_valid_svom_sku(value: str | None) -> bool:
    return bool(SVOM_SKU_RE.fullmatch(str(value or "").strip()))


def build_deterministic_svom_sku(*, product_id: str | UUID, counter: int = 0) -> str:
    normalized_id = str(UUID(str(product_id)))
    seed = f"{normalized_id}:{int(counter)}".encode("utf-8")
    digest = hashlib.sha256(seed).digest()
    digits = [str(byte % 10) for byte in digest[:8]]
    return f"{digits[0]}S{digits[1]}V{digits[2]}O{digits[3]}M{digits[4]}{digits[5]}{digits[6]}{digits[7]}"


def resolve_unique_svom_sku(product: Product, *, max_attempts: int = 10_000) -> tuple[str, int]:
    existing = str(getattr(product, "svom_sku", "") or "").strip()
    if existing:
        return existing, 0

    for counter in range(max_attempts):
        candidate = build_deterministic_svom_sku(product_id=product.id, counter=counter)
        collision = Product.objects.filter(svom_sku=candidate).exclude(id=product.id).exists()
        if not collision:
            return candidate, counter

    raise RuntimeError(f"Unable to allocate unique SVOM SKU for product={product.id}")


def ensure_product_svom_sku(product: Product, *, save: bool = True) -> tuple[str, int, bool]:
    existing = str(getattr(product, "svom_sku", "") or "").strip()
    if existing:
        return existing, 0, False

    candidate, counter = resolve_unique_svom_sku(product)
    product.svom_sku = candidate
    if save:
        product.save(update_fields=["svom_sku", "updated_at"])
    return candidate, counter, True
