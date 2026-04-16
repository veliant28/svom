from apps.catalog.models import Product


def build_product_document(product: Product) -> dict:
    product_price = getattr(product, "product_price", None)
    return {
        "id": str(product.id),
        "sku": product.sku,
        "article": product.article,
        "name": product.name,
        "slug": product.slug,
        "brand_name": product.brand.name,
        "brand_slug": product.brand.slug,
        "category_name": product.category.name,
        "category_slug": product.category.slug,
        "is_active": product.is_active,
        "is_featured": product.is_featured,
        "is_new": product.is_new,
        "is_bestseller": product.is_bestseller,
        "final_price": float(product_price.final_price) if product_price else None,
        "currency": product_price.currency if product_price else None,
    }
