from django.urls import path

from apps.catalog.api.views import (
    BrandListAPIView,
    CategoryListAPIView,
    HeaderNavigationAPIView,
    ProductDetailAPIView,
    ProductFitmentOptionsAPIView,
    ProductFitmentRowsAPIView,
    ProductListAPIView,
    ProductSellableSnapshotAPIView,
)

app_name = "catalog_api"

urlpatterns = [
    path("brands/", BrandListAPIView.as_view(), name="brand-list"),
    path("categories/", CategoryListAPIView.as_view(), name="category-list"),
    path("navigation/header/", HeaderNavigationAPIView.as_view(), name="header-navigation"),
    path("products/", ProductListAPIView.as_view(), name="product-list"),
    path("products/<slug:slug>/", ProductDetailAPIView.as_view(), name="product-detail"),
    path("products/<slug:slug>/fitment-options/", ProductFitmentOptionsAPIView.as_view(), name="product-fitment-options"),
    path(
        "products/<slug:slug>/compatibility/options/",
        ProductFitmentOptionsAPIView.as_view(),
        name="product-compatibility-options",
    ),
    path("products/<slug:slug>/fitments/", ProductFitmentRowsAPIView.as_view(), name="product-fitment-rows"),
    path("products/<slug:slug>/sellable/", ProductSellableSnapshotAPIView.as_view(), name="product-sellable"),
]
