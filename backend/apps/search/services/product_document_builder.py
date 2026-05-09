from apps.catalog.models import Product


def build_product_document(product: Product) -> dict:
    product_price = getattr(product, "product_price", None)
    brand = getattr(product, "brand", None)
    category = getattr(product, "category", None)
    return {
        "id": str(product.id),
        "sku": product.sku,
        "article": product.article,
        "name": product.name,
        "slug": product.slug,
        "brand_name": brand.name if brand else "",
        "brand_slug": brand.slug if brand else "",
        "category_name": category.name if category else "",
        "category_slug": category.slug if category else "",
        "is_active": product.is_active,
        "is_featured": product.is_featured,
        "is_new": product.is_new,
        "is_bestseller": product.is_bestseller,
        "final_price": float(product_price.final_price) if product_price else None,
        "currency": product_price.currency if product_price else None,
    }
