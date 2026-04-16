# SVOM 3.0 Django Admin -> Backoffice Audit

Last updated: 2026-04-13

## 1) Where Django Admin is still used

- Route: `backend/config/urls.py` -> `path("admin/", admin_site.urls)`
- App config: `backend/config/settings/base.py` -> `apps.core.admin.apps.SVOMAdminConfig` in `INSTALLED_APPS`
- Custom admin site:
  - `backend/apps/core/admin/site.py`
  - `backend/apps/core/admin/apps.py`
- Admin sidebar config with `admin:*` links:
  - `backend/config/settings/base.py` (`UNFOLD.SIDEBAR.navigation`)
- Admin actions/mixins:
  - `backend/apps/core/admin/actions.py`
  - `backend/apps/pricing/admin/supplier_admin.py`
  - `backend/apps/pricing/admin/supplier_offer_admin.py`
  - `backend/apps/supplier_imports/admin/import_source_admin.py`
- Inline admin forms:
  - `backend/apps/supplier_imports/admin/import_run_admin.py` (`ImportArtifactInline`, `ImportRowErrorInline`)

## 2) Admin entity parity matrix

Legend:
- `Done` - backoffice page + API covers operational usage.
- `Partial` - covered for operations, but not full admin CRUD/actions or not complete details.
- `Missing` - still admin-only.

### Catalog / pricing / imports / orders

| Admin entity | Backoffice status | Notes |
|---|---|---|
| `catalog.Brand` | Done | CRUD + filters/search + reprice action |
| `catalog.Category` | Done | CRUD + filters/search + reprice action |
| `catalog.Product` | Done | CRUD + filters/search + bulk actions reprice/reindex |
| `autocatalog.CarModification` | Done (read model) | Backoffice list with filters/search/pagination/i18n |
| `pricing.Supplier` | Partial | Workspace + operational flows + supplier reprice by code; no dedicated full CRUD grid yet |
| `pricing.SupplierOffer` | Partial | Operational list exists; no full admin-equivalent editing |
| `pricing.ProductPrice` | Partial | Operational list exists; no full admin-equivalent editing |
| `supplier_imports.ImportSource` | Partial | list/schedule/update + run actions; not full admin editor parity |
| `supplier_imports.ImportRun` | Partial | list/detail parity; inline artifact/error is represented by separate screens |
| `supplier_imports.ImportRunQuality` | Done | summary/list/detail/compare in backoffice |
| `supplier_imports.SupplierRawOffer` | Done | list + matching workflows |
| `supplier_imports.OfferMatchReview` | Done/Partial | covered by matching pages, not as direct admin changelist |
| `supplier_imports.SupplierBrandAlias` | Done | list/create/update |
| `supplier_imports.ArticleNormalizationRule` | Done | list/create/update |
| `supplier_imports.ImportRowError` | Done | list with filters |
| `commerce.Order` / `commerce.OrderItem` | Done | operational list/detail/actions in backoffice |

### Vehicles / compatibility

| Admin entity | Backoffice status | Notes |
|---|---|---|
| `vehicles.VehicleMake` | Excluded from active UI | Vehicle manager routes are removed from current product scope |
| `vehicles.VehicleModel` | Excluded from active UI | Kept out of operational navigation and locale routes |
| `vehicles.VehicleGeneration` | Excluded from active UI | Kept out of operational navigation and locale routes |
| `vehicles.VehicleEngine` | Excluded from active UI | Kept out of operational navigation and locale routes |
| `vehicles.VehicleModification` | Excluded from active UI | Kept out of operational navigation and locale routes |
| `compatibility.ProductFitment` | Excluded from active UI | Compatibility manager routes are removed from active scope |

### Still admin-only (migration backlog)

| Admin entity | Status |
|---|---|
| `catalog.Attribute` | Missing |
| `catalog.AttributeValue` | Missing |
| `catalog.ProductAttribute` | Missing |
| `catalog.ProductImage` | Missing |
| `marketing.HeroSlide` | Missing |
| `marketing.HeroSliderSettings` | Missing |
| `marketing.PromoBanner` | Missing |
| `marketing.PromoBannerSettings` | Missing |
| `pricing.PricingPolicy` | Missing |
| `pricing.PricingRule` | Missing |
| `pricing.PriceOverride` | Missing |
| `pricing.CurrencyRate` | Missing |
| `pricing.PriceHistory` | Missing |
| `supplier_imports.ImportArtifact` | Missing (standalone page) |
| `supplier_imports.SupplierIntegration` | Partial (some settings in workspace) |
| `users.User` | Missing |
| `users.GarageVehicle` | Missing |
| `commerce.Cart` | Missing |
| `commerce.CartItem` | Missing |
| `commerce.WishlistItem` | Missing |

## 3) Implemented in this migration step

- Removed from active frontend scope (product decision):
  - vehicle manager section
  - compatibility manager section
  - standalone import-source manager section
- Removed corresponding unused backoffice i18n modules for those sections.
- Added smoke tests:
  - `apps.backoffice.tests.test_vehicle_taxonomy_api_smoke`
  - `apps.backoffice.tests.test_product_fitments_api_smoke`

## 4) Permissions and access checks

- Backoffice API is protected by:
  - `TokenAuthentication`
  - `IsAuthenticated`
  - `IsStaffOrSuperuser`
- Current check is centralized in:
  - `backend/apps/backoffice/api/views/_base.py`
  - `backend/apps/backoffice/permissions/staff_permission.py`

## 5) Why Django Admin is not removed yet

Admin route and registrations are intentionally still present because parity is not 100%.

Blocking gaps before final removal:
- missing backoffice modules for entities listed under `Missing`
- remaining `Partial` sections need full operational parity
- only after that:
  1. remove all manager workflows from admin,
  2. disable `/admin/` route,
  3. remove admin registrations and `SVOMAdminConfig` from runtime usage.
