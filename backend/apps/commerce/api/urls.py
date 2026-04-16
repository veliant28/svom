from django.urls import path

from apps.commerce.api.views import (
    CartItemCreateAPIView,
    CartItemUpdateDeleteAPIView,
    CartRetrieveAPIView,
    CheckoutPreviewAPIView,
    CheckoutSubmitAPIView,
    OrderListAPIView,
    WishlistItemCreateAPIView,
    WishlistItemDeleteAPIView,
    WishlistListAPIView,
)

app_name = "commerce_api"

urlpatterns = [
    path("wishlist/", WishlistListAPIView.as_view(), name="wishlist-list"),
    path("wishlist/items/", WishlistItemCreateAPIView.as_view(), name="wishlist-item-create"),
    path("wishlist/items/<uuid:item_id>/", WishlistItemDeleteAPIView.as_view(), name="wishlist-item-delete"),
    path("cart/", CartRetrieveAPIView.as_view(), name="cart-retrieve"),
    path("cart/items/", CartItemCreateAPIView.as_view(), name="cart-item-create"),
    path("cart/items/<uuid:item_id>/", CartItemUpdateDeleteAPIView.as_view(), name="cart-item-update-delete"),
    path("checkout/preview/", CheckoutPreviewAPIView.as_view(), name="checkout-preview"),
    path("checkout/submit/", CheckoutSubmitAPIView.as_view(), name="checkout-submit"),
    path("orders/", OrderListAPIView.as_view(), name="order-list"),
]
