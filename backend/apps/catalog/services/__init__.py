from .brand_management import (
    find_brand_by_normalized_name,
    generate_unique_brand_slug,
    normalized_brand_name,
    sanitize_brand_name,
)
from .autodb_category_mapping import resolve_autodb_category_for_raw_offer
from .autodb_content import (
    build_autodb_characteristic_attributes,
    get_autodb_primary_image_url,
    get_autodb_product_content,
    resolve_autodb_article_name,
    resolve_autodb_category_candidates,
)
from .category_management import (
    find_category_by_normalized_name,
    generate_unique_category_slug,
    normalized_category_name,
    sanitize_category_name,
)
from .category_i18n import (
    build_category_i18n_names,
    translate_category_name_uk_to_en,
    translate_category_name_uk_to_ru,
)
from .fitment_filtering import (
    FITMENT_ALL,
    FITMENT_ONLY,
    FITMENT_UNKNOWN,
    FITMENT_WITH_DATA,
    FitmentFilteringService,
)
from .product_management import (
    build_product_public_name_fallback,
    cleanup_product_display_candidate,
    get_product_display_name,
    get_product_display_name_with_meta,
    get_admin_display_name,
    generate_unique_product_slug,
    is_code_like_product_name,
    resolve_locale,
    sanitize_product_name,
)

__all__ = [
    "sanitize_brand_name",
    "normalized_brand_name",
    "find_brand_by_normalized_name",
    "generate_unique_brand_slug",
    "sanitize_category_name",
    "normalized_category_name",
    "find_category_by_normalized_name",
    "generate_unique_category_slug",
    "build_category_i18n_names",
    "translate_category_name_uk_to_ru",
    "translate_category_name_uk_to_en",
    "FitmentFilteringService",
    "FITMENT_ONLY",
    "FITMENT_ALL",
    "FITMENT_UNKNOWN",
    "FITMENT_WITH_DATA",
    "sanitize_product_name",
    "is_code_like_product_name",
    "cleanup_product_display_candidate",
    "get_product_display_name",
    "get_product_display_name_with_meta",
    "build_product_public_name_fallback",
    "resolve_locale",
    "get_admin_display_name",
    "generate_unique_product_slug",
    "get_autodb_product_content",
    "get_autodb_primary_image_url",
    "build_autodb_characteristic_attributes",
    "resolve_autodb_category_candidates",
    "resolve_autodb_article_name",
    "resolve_autodb_category_for_raw_offer",
]
