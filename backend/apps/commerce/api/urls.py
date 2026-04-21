from django.urls import path

from apps.commerce.api.views import (
    CartItemCreateAPIView,
    CartItemUpdateDeleteAPIView,
    CartRetrieveAPIView,
    CheckoutMonobankSelectorWidgetAPIView,
    CheckoutPromoApplyAPIView,
    CheckoutPromoClearAPIView,
    CheckoutNovaPoshtaSettlementsLookupAPIView,
    CheckoutNovaPoshtaStreetsLookupAPIView,
    CheckoutNovaPoshtaWarehousesLookupAPIView,
    CheckoutOrderMonobankWidgetAPIView,
    CheckoutPreviewAPIView,
    CheckoutSubmitAPIView,
    LiqPayWebhookAPIView,
    LoyaltyMyPromoCodesAPIView,
    MonobankWebhookAPIView,
    OrderDetailAPIView,
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
    path("checkout/promo/apply/", CheckoutPromoApplyAPIView.as_view(), name="checkout-promo-apply"),
    path("checkout/promo/clear/", CheckoutPromoClearAPIView.as_view(), name="checkout-promo-clear"),
    path("checkout/submit/", CheckoutSubmitAPIView.as_view(), name="checkout-submit"),
    path(
        "checkout/monobank-selector-widget/",
        CheckoutMonobankSelectorWidgetAPIView.as_view(),
        name="checkout-monobank-selector-widget",
    ),
    path(
        "checkout/orders/<uuid:order_id>/monobank-widget/",
        CheckoutOrderMonobankWidgetAPIView.as_view(),
        name="checkout-order-monobank-widget",
    ),
    path("payments/monobank/webhook/", MonobankWebhookAPIView.as_view(), name="payments-monobank-webhook"),
    path("payments/liqpay/webhook/", LiqPayWebhookAPIView.as_view(), name="payments-liqpay-webhook"),
    path(
        "checkout/lookups/nova-poshta/settlements/",
        CheckoutNovaPoshtaSettlementsLookupAPIView.as_view(),
        name="checkout-lookup-nova-poshta-settlements",
    ),
    path(
        "checkout/lookups/nova-poshta/warehouses/",
        CheckoutNovaPoshtaWarehousesLookupAPIView.as_view(),
        name="checkout-lookup-nova-poshta-warehouses",
    ),
    path(
        "checkout/lookups/nova-poshta/streets/",
        CheckoutNovaPoshtaStreetsLookupAPIView.as_view(),
        name="checkout-lookup-nova-poshta-streets",
    ),
    path("orders/", OrderListAPIView.as_view(), name="order-list"),
    path("orders/<uuid:pk>/", OrderDetailAPIView.as_view(), name="order-detail"),
    path("loyalty/my-codes/", LoyaltyMyPromoCodesAPIView.as_view(), name="loyalty-my-codes"),
]
