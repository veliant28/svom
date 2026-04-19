from __future__ import annotations

from .normalizers import normalize_article_value, normalize_brand_value


def select_candidate_ids(*, details: list[dict], normalized_article: str, normalized_brand: str) -> list[str]:
    strict_ids: set[str] = set()
    relaxed_ids: set[str] = set()

    for item in details:
        detail_id = str(item.get("id") or "").strip()
        if not detail_id.isdigit():
            continue

        detail_article = normalize_article_value(str(item.get("article") or item.get("oem") or ""))
        detail_brand = normalize_brand_value(
            str(item.get("displayBrand") or (item.get("brand") or {}).get("name") or "")
        )

        if detail_article == normalized_article:
            relaxed_ids.add(detail_id)
            if not normalized_brand or not detail_brand or detail_brand == normalized_brand:
                strict_ids.add(detail_id)

    if strict_ids:
        return sorted(strict_ids)
    return sorted(relaxed_ids)
