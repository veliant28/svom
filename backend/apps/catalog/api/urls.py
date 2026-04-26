from django.urls import path

from apps.catalog.api.views import (
    BrandListAPIView,
    CategoryListAPIView,
    ProductDetailAPIView,
    ProductFitmentOptionsAPIView,
    ProductFitmentRowsAPIView,
    ProductListAPIView,
    ProductSellableSnapshotAPIView,
    ProductUtrEnrichmentAPIView,
)

app_name = "catalog_api"

urlpatterns = [
    path("brands/", BrandListAPIView.as_view(), name="brand-list"),
    path("categories/", CategoryListAPIView.as_view(), name="category-list"),
    path("products/", ProductListAPIView.as_view(), name="product-list"),
    path("products/utr-enrichment/", ProductUtrEnrichmentAPIView.as_view(), name="product-utr-enrichment"),
    path("products/<slug:slug>/", ProductDetailAPIView.as_view(), name="product-detail"),
    path("products/<slug:slug>/fitment-options/", ProductFitmentOptionsAPIView.as_view(), name="product-fitment-options"),
    path("products/<slug:slug>/fitments/", ProductFitmentRowsAPIView.as_view(), name="product-fitment-rows"),
    path("products/<slug:slug>/sellable/", ProductSellableSnapshotAPIView.as_view(), name="product-sellable"),
]
