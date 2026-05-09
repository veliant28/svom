from __future__ import annotations

import re
from typing import Literal

from apps.catalog.models import Category

STRICT_FITMENT = "strict_fitment"
SHOW_ALL_WITH_BADGES = "show_all_with_badges"

VehicleFilterPolicy = Literal["strict_fitment", "show_all_with_badges"]

EXEMPT_ROOT_SLUGS = {
    "kolesa-i-shiny",
    "avtohimiia-i-aksessuary",
}

# Legacy/manual taxonomy aliases kept so old seeded/test categories keep the
# same runtime behavior while the public contract uses the canonical slugs.
EXEMPT_ROOT_SIGNATURES = {
    "автохіміятааксесуари",
    "автохимияиаксессуары",
    "autochemicalsandaccessories",
    "kolesaishiny",
    "колесаишины",
    "шинитадиски",
    "шиныидиски",
    "tiresandwheels",
}


def normalize_category_signature(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    return re.sub(r"[^0-9a-zа-яіїєґ]+", "", raw, flags=re.IGNORECASE)


def is_vehicle_filter_exempt_category(category: Category | None) -> bool:
    current = category
    visited: set[str] = set()
    while current is not None:
        category_id = str(current.id)
        if category_id in visited:
            break
        visited.add(category_id)

        slug = str(getattr(current, "slug", "") or "").strip()
        if slug in EXEMPT_ROOT_SLUGS:
            return True

        candidates = (
            slug,
            getattr(current, "name", ""),
            getattr(current, "name_uk", ""),
            getattr(current, "name_ru", ""),
            getattr(current, "name_en", ""),
        )
        for candidate in candidates:
            signature = normalize_category_signature(candidate)
            if signature and signature in EXEMPT_ROOT_SIGNATURES:
                return True

        current = getattr(current, "parent", None)

    return False


def get_vehicle_filter_policy(category: Category | None) -> VehicleFilterPolicy:
    if is_vehicle_filter_exempt_category(category):
        return SHOW_ALL_WITH_BADGES
    return STRICT_FITMENT
