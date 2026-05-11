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
from .category_assignment import (
    assignable_category_or_none,
    can_assign_products_to_category,
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
from .product_branding import (
    ProductBrandDisplay,
    get_product_display_brand,
    get_product_display_brand_payload,
)
from .product_sku import (
    get_product_manufacturer_article,
    get_product_display_sku,
    get_product_internal_import_key,
    is_gpl_product,
    is_multi_offer_product,
)
from .svom_sku import ensure_product_svom_sku, is_valid_svom_sku, build_deterministic_svom_sku
from .category_canonicalization import (
    CANONICAL_CATEGORY_SPECS,
    CanonicalCategorySpec,
    canonical_specs_by_slug,
    find_semantic_category_under_parent,
    resolve_canonical_display_name,
    resolve_canonical_spec_for_name,
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
    "can_assign_products_to_category",
    "assignable_category_or_none",
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
    "ProductBrandDisplay",
    "get_product_display_brand",
    "get_product_display_brand_payload",
    "get_product_display_sku",
    "get_product_manufacturer_article",
    "get_product_internal_import_key",
    "is_gpl_product",
    "is_multi_offer_product",
    "ensure_product_svom_sku",
    "is_valid_svom_sku",
    "build_deterministic_svom_sku",
    "CanonicalCategorySpec",
    "CANONICAL_CATEGORY_SPECS",
    "canonical_specs_by_slug",
    "resolve_canonical_spec_for_name",
    "resolve_canonical_display_name",
    "find_semantic_category_under_parent",
    "get_autodb_product_content",
    "get_autodb_primary_image_url",
    "build_autodb_characteristic_attributes",
    "resolve_autodb_category_candidates",
    "resolve_autodb_article_name",
    "resolve_autodb_category_for_raw_offer",
]
