from apps.catalog.models import Product


def build_product_document(product: Product) -> dict:
    product_price = getattr(product, "product_price", None)
    category = getattr(product, "category", None)
    brand_name = str(
        getattr(product, "display_brand_name", "")
        or getattr(product, "autodb_supplier_name", "")
        or ""
    ).strip()
    return {
        "id": str(product.id),
        "sku": product.sku,
        "svom_sku": product.svom_sku or "",
        "article": product.article,
        "name": product.name,
        "slug": product.slug,
        "brand_name": brand_name,
        "brand_slug": "",
        "category_name": category.name if category else "",
        "category_slug": category.slug if category else "",
        "is_active": product.is_active,
        "is_featured": product.is_featured,
        "is_new": product.is_new,
        "is_bestseller": product.is_bestseller,
        "final_price": float(product_price.final_price) if product_price else None,
        "currency": product_price.currency if product_price else None,
    }
