from apps.pricing.models import Supplier
from apps.supplier_imports.models import ImportSource
from apps.supplier_imports.services.normalization import ArticleNormalizerService, BrandAliasResolverService


def normalize_article(value: str | None, *, source: ImportSource | None = None) -> str:
    return ArticleNormalizerService().normalize(article=value or "", source=source).normalized_article


def normalize_brand(
    value: str | None,
    *,
    source: ImportSource | None = None,
    supplier: Supplier | None = None,
) -> str:
    return BrandAliasResolverService().resolve(
        brand_name=value or "",
        source=source,
        supplier=supplier,
    ).normalized_brand


__all__ = ["normalize_article", "normalize_brand"]
