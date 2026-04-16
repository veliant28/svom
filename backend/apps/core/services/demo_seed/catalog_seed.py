from __future__ import annotations

from dataclasses import dataclass

from apps.catalog.models import Brand, Category, Product, ProductImage
from apps.core.services.demo_seed.media import ensure_placeholder_media_file


@dataclass(frozen=True)
class CatalogSeedData:
    brands: list[Brand]
    categories: list[Category]
    products: list[Product]
    stats: dict[str, int]


def seed_catalog_demo() -> CatalogSeedData:
    brands = _seed_brands()
    categories = _seed_categories()
    products = _seed_products(brands, categories)
    product_images_count = _seed_product_images(products)

    stats = {
        "brands": len(brands),
        "categories": len(categories),
        "products": len(products),
        "product_images": product_images_count,
    }
    return CatalogSeedData(brands=brands, categories=categories, products=products, stats=stats)


def _seed_brands() -> list[Brand]:
    payload = [
        {"slug": "bosch", "name": "Bosch", "country": "Germany"},
        {"slug": "mann-filter", "name": "MANN-FILTER", "country": "Germany"},
        {"slug": "castrol", "name": "Castrol", "country": "United Kingdom"},
        {"slug": "osram", "name": "OSRAM", "country": "Germany"},
    ]

    result: list[Brand] = []
    for item in payload:
        brand, _ = Brand.objects.update_or_create(
            slug=item["slug"],
            defaults={
                "name": item["name"],
                "country": item["country"],
                "is_active": True,
                "description": f"Demo brand: {item['name']}",
            },
        )
        result.append(brand)
    return result


def _seed_categories() -> list[Category]:
    root_categories = [
        {"slug": "filters", "name": "Filters"},
        {"slug": "oils-fluids", "name": "Oils & Fluids"},
        {"slug": "lighting", "name": "Lighting"},
    ]

    result: list[Category] = []
    roots_by_slug: dict[str, Category] = {}

    for item in root_categories:
        category, _ = Category.objects.update_or_create(
            slug=item["slug"],
            defaults={
                "name": item["name"],
                "parent": None,
                "is_active": True,
                "description": f"Demo category: {item['name']}",
            },
        )
        result.append(category)
        roots_by_slug[item["slug"]] = category

    child_categories = [
        {"slug": "oil-filters", "name": "Oil Filters", "parent_slug": "filters"},
        {"slug": "engine-oil", "name": "Engine Oil", "parent_slug": "oils-fluids"},
        {"slug": "headlight-bulbs", "name": "Headlight Bulbs", "parent_slug": "lighting"},
    ]

    for item in child_categories:
        category, _ = Category.objects.update_or_create(
            slug=item["slug"],
            defaults={
                "name": item["name"],
                "parent": roots_by_slug[item["parent_slug"]],
                "is_active": True,
                "description": f"Demo category: {item['name']}",
            },
        )
        result.append(category)

    return result


def _seed_products(brands: list[Brand], categories: list[Category]) -> list[Product]:
    brands_by_slug = {brand.slug: brand for brand in brands}
    categories_by_slug = {category.slug: category for category in categories}

    payload = [
        {
            "sku": "BOS-F026407123",
            "article": "F026407123",
            "slug": "bosch-oil-filter-f026407123",
            "name": "Bosch Oil Filter F 026 407 123",
            "brand_slug": "bosch",
            "category_slug": "oil-filters",
            "short_description": "Reliable oil filter for daily urban driving.",
        },
        {
            "sku": "MAN-W71295",
            "article": "W 712/95",
            "slug": "mann-filter-w-712-95",
            "name": "MANN-FILTER W 712/95",
            "brand_slug": "mann-filter",
            "category_slug": "oil-filters",
            "short_description": "High efficiency filtration for modern engines.",
        },
        {
            "sku": "CAS-EDGE-5W30-4L",
            "article": "EDGE5W304L",
            "slug": "castrol-edge-5w30-4l",
            "name": "Castrol EDGE 5W-30 4L",
            "brand_slug": "castrol",
            "category_slug": "engine-oil",
            "short_description": "Synthetic engine oil for performance engines.",
        },
        {
            "sku": "OSR-H7-64210",
            "article": "64210",
            "slug": "osram-original-h7-64210",
            "name": "OSRAM ORIGINAL H7 64210",
            "brand_slug": "osram",
            "category_slug": "headlight-bulbs",
            "short_description": "Standard halogen bulb with stable luminous flux.",
        },
        {
            "sku": "BOS-AIR-S1988",
            "article": "S1988",
            "slug": "bosch-air-filter-s1988",
            "name": "Bosch Air Filter S1988",
            "brand_slug": "bosch",
            "category_slug": "filters",
            "short_description": "Air filter for stable intake airflow and reduced dust.",
        },
        {
            "sku": "CAS-MAGN-5W40-4L",
            "article": "MAGN5W404L",
            "slug": "castrol-magnatec-5w40-4l",
            "name": "Castrol MAGNATEC 5W-40 4L",
            "brand_slug": "castrol",
            "category_slug": "engine-oil",
            "short_description": "Synthetic oil for stop-start city cycles and longer protection.",
        },
    ]

    result: list[Product] = []
    for index, item in enumerate(payload, start=1):
        product, _ = Product.objects.update_or_create(
            sku=item["sku"],
            defaults={
                "article": item["article"],
                "slug": item["slug"],
                "name": item["name"],
                "brand": brands_by_slug[item["brand_slug"]],
                "category": categories_by_slug[item["category_slug"]],
                "short_description": item["short_description"],
                "description": f"Demo product description for {item['name']}.",
                "is_active": True,
                "is_featured": index in (1, 3),
                "is_new": index in (2, 4),
                "is_bestseller": index == 1,
            },
        )
        result.append(product)

    return result


def _seed_product_images(products: list[Product]) -> int:
    created_or_updated = 0
    for index, product in enumerate(products, start=1):
        image_path = ensure_placeholder_media_file(
            f"catalog/products/images/demo-product-{index}.png"
        )
        _, _ = ProductImage.objects.update_or_create(
            product=product,
            sort_order=0,
            defaults={
                "image": image_path,
                "alt_text": product.name,
                "is_primary": True,
            },
        )
        created_or_updated += 1
    return created_or_updated
