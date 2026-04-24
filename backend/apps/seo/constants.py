from __future__ import annotations

SEO_LOCALE_CHOICES: tuple[tuple[str, str], ...] = (
    ("uk", "Ukrainian"),
    ("ru", "Russian"),
    ("en", "English"),
)

SEO_ENTITY_TYPE_CHOICES: tuple[tuple[str, str], ...] = (
    ("product", "Product"),
    ("category", "Category"),
    ("brand", "Brand"),
    ("page", "Page"),
)

SEO_ALLOWED_TEMPLATE_PLACEHOLDERS: tuple[str, ...] = (
    "{name}",
    "{brand}",
    "{category}",
    "{article}",
    "{price}",
    "{site_name}",
)

SEO_DEFAULT_ROBOTS_DIRECTIVE = "index,follow"

DEFAULT_GOOGLE_EVENT_DEFINITIONS: tuple[tuple[str, str, str], ...] = (
    ("view_item", "View item", "Product detail view."),
    ("add_to_cart", "Add to cart", "Add product to cart."),
    ("begin_checkout", "Begin checkout", "Checkout started."),
    ("purchase", "Purchase", "Successful order payment."),
    ("refund", "Refund", "Order refund."),
    ("search", "Search", "Catalog search."),
    ("view_item_list", "View item list", "Product list/category view."),
)
