from apps.pricing.models import Supplier
from apps.supplier_imports.parsers.utils import normalize_article as simple_normalize_article
from apps.supplier_imports.parsers.utils import normalize_brand as simple_normalize_brand
from apps.supplier_imports.models import ImportSource
from apps.supplier_imports.services.normalization import ArticleNormalizerService, BrandAliasResolverService


def normalize_article(value: str | None, *, source: ImportSource | None = None) -> str:
    if source is None:
        return simple_normalize_article(value or "")
    return ArticleNormalizerService().normalize(article=value or "", source=source).normalized_article


def normalize_brand(
    value: str | None,
    *,
    source: ImportSource | None = None,
    supplier: Supplier | None = None,
) -> str:
    if source is None and supplier is None:
        return simple_normalize_brand(value or "")
    return BrandAliasResolverService().resolve(
        brand_name=value or "",
        source=source,
        supplier=supplier,
    ).normalized_brand


__all__ = ["normalize_article", "normalize_brand"]
