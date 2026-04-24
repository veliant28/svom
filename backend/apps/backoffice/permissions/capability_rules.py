from __future__ import annotations

from dataclasses import dataclass


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@dataclass(frozen=True)
class BackofficeCapabilityRule:
    prefix: str
    read_capabilities: tuple[str, ...]
    write_capabilities: tuple[str, ...]


RULES: tuple[BackofficeCapabilityRule, ...] = (
    BackofficeCapabilityRule("users/", ("users.view",), ("users.manage",)),
    BackofficeCapabilityRule("groups/", ("groups.view",), ("groups.manage",)),
    BackofficeCapabilityRule("summary/", ("backoffice.access",), ("backoffice.access",)),
    BackofficeCapabilityRule("payments/", ("payments.view",), ("payments.view",)),
    BackofficeCapabilityRule("settings/hero-block/", ("promo_banners.manage",), ("promo_banners.manage",)),
    BackofficeCapabilityRule("settings/promo-banners/", ("promo_banners.manage",), ("promo_banners.manage",)),
    BackofficeCapabilityRule("settings/footer/", ("footer.settings",), ("footer.settings",)),
    BackofficeCapabilityRule("procurement/", ("procurement.manage",), ("procurement.manage",)),
    BackofficeCapabilityRule("orders/", ("orders.view", "customers.support"), ("orders.manage", "customers.support")),
    BackofficeCapabilityRule("nova-poshta/senders/", ("nova_poshta.settings",), ("nova_poshta.settings",)),
    BackofficeCapabilityRule("suppliers/", ("suppliers.view",), ("suppliers.manage",)),
    BackofficeCapabilityRule("supplier-offers/", ("suppliers.view",), ("suppliers.manage",)),
    BackofficeCapabilityRule("raw-offers/", ("suppliers.view",), ("suppliers.manage",)),
    BackofficeCapabilityRule("import-sources/", ("imports.view",), ("imports.manage",)),
    BackofficeCapabilityRule("import-schedules/", ("schedules.view",), ("schedules.view",)),
    BackofficeCapabilityRule("import-runs/", ("imports.view",), ("imports.manage",)),
    BackofficeCapabilityRule("import-errors/", ("imports.view",), ("imports.manage",)),
    BackofficeCapabilityRule("import-quality/", ("imports.view",), ("imports.manage",)),
    BackofficeCapabilityRule("actions/run-source/", ("imports.manage",), ("imports.manage",)),
    BackofficeCapabilityRule("actions/import-all/", ("imports.manage",), ("imports.manage",)),
    BackofficeCapabilityRule("actions/reprice-after-import/", ("imports.manage",), ("imports.manage",)),
    BackofficeCapabilityRule("actions/reindex-products/", ("imports.manage",), ("imports.manage",)),
    BackofficeCapabilityRule("actions/bulk-move-products-category/", ("catalog.manage",), ("catalog.manage",)),
    BackofficeCapabilityRule("product-prices/", ("pricing.view",), ("pricing.manage",)),
    BackofficeCapabilityRule("pricing/", ("pricing.view",), ("pricing.manage",)),
    BackofficeCapabilityRule("loyalty/", ("loyalty.issue",), ("loyalty.issue",)),
    BackofficeCapabilityRule("support/", ("customers.support",), ("customers.support",)),
    BackofficeCapabilityRule("autocatalog/", ("autocatalog.view",), ("autocatalog.view",)),
    BackofficeCapabilityRule("brands/", ("brands.view",), ("brands.view",)),
    BackofficeCapabilityRule("categories/", ("categories.view",), ("categories.view",)),
    BackofficeCapabilityRule("products/", ("catalog.view",), ("catalog.manage",)),
    BackofficeCapabilityRule("vehicle-makes/", ("catalog.view",), ("catalog.manage",)),
    BackofficeCapabilityRule("vehicle-models/", ("catalog.view",), ("catalog.manage",)),
    BackofficeCapabilityRule("vehicle-generations/", ("catalog.view",), ("catalog.manage",)),
    BackofficeCapabilityRule("vehicle-engines/", ("catalog.view",), ("catalog.manage",)),
    BackofficeCapabilityRule("vehicle-modifications/", ("catalog.view",), ("catalog.manage",)),
    BackofficeCapabilityRule("product-fitments/", ("catalog.view",), ("catalog.manage",)),
    BackofficeCapabilityRule("article-rules/", ("catalog.view",), ("catalog.manage",)),
    BackofficeCapabilityRule("brand-aliases/", ("catalog.view",), ("catalog.manage",)),
)


def normalize_backoffice_path(path: str) -> str:
    normalized = str(path or "").strip()
    marker = "/api/backoffice/"
    if marker in normalized:
        normalized = normalized.split(marker, 1)[1]
    normalized = normalized.lstrip("/")
    return normalized


def resolve_required_capabilities_for_request(path: str, method: str) -> tuple[str, ...]:
    normalized_path = normalize_backoffice_path(path)
    normalized_method = str(method or "").upper()

    for rule in RULES:
        if normalized_path.startswith(rule.prefix):
            if normalized_method in SAFE_METHODS:
                return rule.read_capabilities
            return rule.write_capabilities

    return ("backoffice.access",)
