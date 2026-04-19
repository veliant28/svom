from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.catalog.models import Brand, Category, Product
from apps.commerce.models import Cart, CartItem, Order, WishlistItem
from apps.pricing.models import ProductPrice
from apps.users.models import User


class CommerceAPISmokeTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="commerce@test.local", username="commerce", password="pass12345")
        self.token = Token.objects.create(user=self.user)
        self.auth = {"HTTP_AUTHORIZATION": f"Token {self.token.key}"}

        self.brand = Brand.objects.create(name="Commerce Brand", slug="commerce-brand", is_active=True)
        self.category = Category.objects.create(name="Commerce Category", slug="commerce-category", is_active=True)
        self.product = Product.objects.create(
            sku="COMM-001",
            article="COMM-001",
            name="Commerce Product",
            slug="commerce-product",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        ProductPrice.objects.create(product=self.product, final_price="123.00", currency="UAH")

    def test_wishlist_add_list_delete_flow(self):
        create_response = self.client.post(
            reverse("commerce_api:wishlist-item-create"),
            {"product_id": str(self.product.id)},
            format="json",
            **self.auth,
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        list_response = self.client.get(reverse("commerce_api:wishlist-list"), **self.auth)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)

        item_id = list_response.data[0]["id"]
        delete_response = self.client.delete(reverse("commerce_api:wishlist-item-delete", kwargs={"item_id": item_id}), **self.auth)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(WishlistItem.objects.filter(user=self.user, product=self.product).exists())

    def test_cart_and_checkout_flow(self):
        add_to_cart_response = self.client.post(
            reverse("commerce_api:cart-item-create"),
            {"product_id": str(self.product.id), "quantity": 2},
            format="json",
            **self.auth,
        )
        self.assertEqual(add_to_cart_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(add_to_cart_response.data["summary"]["items_count"], 2)

        cart_item_id = add_to_cart_response.data["items"][0]["id"]

        update_response = self.client.patch(
            reverse("commerce_api:cart-item-update-delete", kwargs={"item_id": cart_item_id}),
            {"quantity": 3},
            format="json",
            **self.auth,
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["summary"]["items_count"], 3)

        preview_response = self.client.get(
            reverse("commerce_api:checkout-preview"),
            {"delivery_method": Order.DELIVERY_COURIER},
            **self.auth,
        )
        self.assertEqual(preview_response.status_code, status.HTTP_200_OK)
        self.assertEqual(preview_response.data["checkout_preview"]["items_count"], 3)

        submit_response = self.client.post(
            reverse("commerce_api:checkout-submit"),
            {
                "contact_full_name": "Commerce Demo",
                "contact_phone": "38(000)111-22-33",
                "contact_email": "commerce@test.local",
                "delivery_method": Order.DELIVERY_COURIER,
                "delivery_address": "Kyiv, Demo street 1",
                "payment_method": Order.PAYMENT_CARD_PLACEHOLDER,
                "customer_comment": "Please call before delivery",
            },
            format="json",
            **self.auth,
        )
        self.assertEqual(submit_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(submit_response.data["status"], Order.STATUS_NEW)

        orders_response = self.client.get(reverse("commerce_api:order-list"), **self.auth)
        self.assertEqual(orders_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(orders_response.data), 1)

        self.assertEqual(Cart.objects.filter(user=self.user).count(), 1)
        self.assertEqual(CartItem.objects.filter(cart__user=self.user).count(), 0)

    def test_checkout_nova_poshta_lookup_requires_sender_profile(self):
        response = self.client.post(
            reverse("commerce_api:checkout-lookup-nova-poshta-settlements"),
            {"query": "Ки", "locale": "uk"},
            format="json",
            **self.auth,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)
