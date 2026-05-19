from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.catalog.models import Brand, Category, Product
from apps.commerce.models import Order, OrderItem, ReturnRequest
from apps.core.selectors import get_return_service_settings
from apps.users.models import User


class CommerceReturnsApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="returns@test.local", first_name="Returns", password="pass12345")
        self.token = Token.objects.create(user=self.user)
        self.auth = {"HTTP_AUTHORIZATION": f"Token {self.token.key}"}

        self.brand = Brand.objects.create(name="RET", slug="ret", is_active=True)
        self.category = Category.objects.create(name="Suspension", slug="suspension", is_active=True)
        self.category_child = Category.objects.create(
            name="Suspension Child",
            slug="suspension-child",
            parent=self.category,
            is_active=True,
        )
        self.product = Product.objects.create(
            sku="RET-001",
            article="RET-001",
            name="Returnable Product",
            slug="returnable-product",
            brand=self.brand,
            category=self.category_child,
            is_active=True,
        )

        self.order = Order.objects.create(
            user=self.user,
            order_number="ORD-RET-0001",
            status=Order.STATUS_COMPLETED,
            contact_full_name="Return User",
            contact_phone="+380671112233",
            contact_email="returns@test.local",
            delivery_method=Order.DELIVERY_NOVA_POSHTA,
            delivery_address="Kyiv",
            payment_method=Order.PAYMENT_CASH_ON_DELIVERY,
            subtotal="1000.00",
            total="1000.00",
            currency="UAH",
            received_at=timezone.now() - timedelta(days=3),
            received_at_source=Order.RECEIVED_SOURCE_ORDER_COMPLETED_FALLBACK,
            return_eligible_until=timezone.now() + timedelta(days=10),
        )
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            product_sku=self.product.sku,
            quantity=2,
            unit_price="500.00",
            line_total="1000.00",
        )

    def _enable_returns(self):
        settings = get_return_service_settings()
        settings.returns_enabled = True
        settings.returns_recipient_full_name = "Receiver"
        settings.returns_recipient_phone = "+380671112233"
        settings.returns_region_label = "Kyivska"
        settings.returns_city_label = "Kyiv"
        settings.returns_np_warehouse_text = "Branch 1"
        settings.save(
            update_fields=(
                "returns_enabled",
                "returns_recipient_full_name",
                "returns_recipient_phone",
                "returns_region_label",
                "returns_city_label",
                "returns_np_warehouse_text",
                "updated_at",
            )
        )

    def test_returns_endpoints_are_blocked_when_service_disabled(self):
        response = self.client.get(reverse("commerce_api:returns-list"), **self.auth)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Сервис возвратов временно недоступен")

    def test_create_return_validates_non_returnable_category(self):
        self._enable_returns()
        settings = get_return_service_settings()
        settings.returns_non_returnable_category_ids = [str(self.category.id)]
        settings.returns_include_subcategories = True
        settings.save(update_fields=("returns_non_returnable_category_ids", "returns_include_subcategories", "updated_at"))

        response = self.client.post(
            reverse("commerce_api:returns-create"),
            {
                "order_id": str(self.order.id),
                "reason_comment": "Need to return this item",
                "items": [{"order_item_id": str(self.order_item.id), "quantity": 1}],
            },
            format="json",
            **self.auth,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("items", response.data)

    def test_create_return_fails_outside_14_day_window(self):
        self._enable_returns()
        self.order.return_eligible_until = timezone.now() - timedelta(minutes=1)
        self.order.save(update_fields=("return_eligible_until", "updated_at"))

        response = self.client.post(
            reverse("commerce_api:returns-create"),
            {
                "order_id": str(self.order.id),
                "reason_comment": "Need to return this item",
                "items": [{"order_item_id": str(self.order_item.id), "quantity": 1}],
            },
            format="json",
            **self.auth,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)

    def test_create_return_fails_when_quantity_exceeds_available(self):
        self._enable_returns()
        response = self.client.post(
            reverse("commerce_api:returns-create"),
            {
                "order_id": str(self.order.id),
                "reason_comment": "Need to return this item",
                "items": [{"order_item_id": str(self.order_item.id), "quantity": 3}],
            },
            format="json",
            **self.auth,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("items", response.data)

    def test_create_return_fails_without_items(self):
        self._enable_returns()
        response = self.client.post(
            reverse("commerce_api:returns-create"),
            {
                "order_id": str(self.order.id),
                "reason_comment": "Need to return this item",
                "items": [],
            },
            format="json",
            **self.auth,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("items", response.data)

    def test_return_number_is_sequential(self):
        self._enable_returns()
        payload = {
            "order_id": str(self.order.id),
            "reason_comment": "Need to return this item",
            "items": [{"order_item_id": str(self.order_item.id), "quantity": 1}],
        }
        first = self.client.post(reverse("commerce_api:returns-create"), payload, format="json", **self.auth)
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second_order = Order.objects.create(
            user=self.user,
            order_number="ORD-RET-0002",
            status=Order.STATUS_COMPLETED,
            contact_full_name="Return User",
            contact_phone="+380671112233",
            contact_email="returns@test.local",
            delivery_method=Order.DELIVERY_NOVA_POSHTA,
            delivery_address="Kyiv",
            payment_method=Order.PAYMENT_CASH_ON_DELIVERY,
            subtotal="500.00",
            total="500.00",
            currency="UAH",
            received_at=timezone.now() - timedelta(days=2),
            received_at_source=Order.RECEIVED_SOURCE_ORDER_COMPLETED_FALLBACK,
            return_eligible_until=timezone.now() + timedelta(days=12),
        )
        second_item = OrderItem.objects.create(
            order=second_order,
            product=self.product,
            product_name=self.product.name,
            product_sku=self.product.sku,
            quantity=1,
            unit_price="500.00",
            line_total="500.00",
        )
        second = self.client.post(
            reverse("commerce_api:returns-create"),
            {
                "order_id": str(second_order.id),
                "reason_comment": "Need to return second item",
                "items": [{"order_item_id": str(second_item.id), "quantity": 1}],
            },
            format="json",
            **self.auth,
        )
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        first_number = str(first.data["return_number"])
        second_number = str(second.data["return_number"])
        self.assertRegex(first_number, r"^RET-\d{6}$")
        self.assertRegex(second_number, r"^RET-\d{6}$")
        self.assertGreater(int(second_number.split("-")[1]), int(first_number.split("-")[1]))

    def test_eligible_orders_response_does_not_expose_received_at(self):
        self._enable_returns()
        response = self.client.get(reverse("commerce_api:returns-eligible-orders"), **self.auth)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data)
        self.assertNotIn("received_at", response.data[0])

    def test_eligible_order_detail_returns_order_currency(self):
        self._enable_returns()
        self.product.svom_sku = "4S0V0O0M0001"
        self.product.save(update_fields=("svom_sku", "updated_at"))
        response = self.client.get(
            reverse("commerce_api:returns-eligible-order-detail", kwargs={"order_id": str(self.order.id)}),
            **self.auth,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["order"]["currency"], "UAH")
        self.assertEqual(response.data["items"][0]["product"]["sku"], "4S0V0O0M0001")
        self.assertEqual(response.data["items"][0]["product"]["article"], "RET-001")

    def test_tracking_requires_14_digits_and_is_saved_normalized(self):
        self._enable_returns()
        create_response = self.client.post(
            reverse("commerce_api:returns-create"),
            {
                "order_id": str(self.order.id),
                "reason_comment": "Need to return this item",
                "items": [{"order_item_id": str(self.order_item.id), "quantity": 1}],
            },
            format="json",
            **self.auth,
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        return_id = create_response.data["id"]

        request_obj = ReturnRequest.objects.get(id=return_id)
        request_obj.status = ReturnRequest.STATUS_APPROVED
        request_obj.save(update_fields=("status", "updated_at"))

        bad_response = self.client.post(
            reverse("commerce_api:returns-tracking-submit", kwargs={"id": return_id}),
            {"tracking_number": "5900 123"},
            format="json",
            **self.auth,
        )
        self.assertEqual(bad_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("tracking_number", bad_response.data)

        ok_response = self.client.post(
            reverse("commerce_api:returns-tracking-submit", kwargs={"id": return_id}),
            {"tracking_number": "59 0015 4190 5785"},
            format="json",
            **self.auth,
        )
        self.assertEqual(ok_response.status_code, status.HTTP_200_OK)
        self.assertEqual(ok_response.data["tracking_number"], "59 0015 4190 5785")

        request_obj.refresh_from_db()
        self.assertEqual(request_obj.customer_return_tracking_number, "59001541905785")
        self.assertEqual(request_obj.status, ReturnRequest.STATUS_IN_TRANSIT)

    def test_tracking_can_be_edited_within_one_hour_after_first_submit(self):
        self._enable_returns()
        create_response = self.client.post(
            reverse("commerce_api:returns-create"),
            {
                "order_id": str(self.order.id),
                "reason_comment": "Need to return this item",
                "items": [{"order_item_id": str(self.order_item.id), "quantity": 1}],
            },
            format="json",
            **self.auth,
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        return_id = create_response.data["id"]

        first_submit_at = timezone.now() - timedelta(minutes=30)
        request_obj = ReturnRequest.objects.get(id=return_id)
        request_obj.status = ReturnRequest.STATUS_IN_TRANSIT
        request_obj.customer_return_tracking_number = "59001541905785"
        request_obj.customer_return_tracking_submitted_at = first_submit_at
        request_obj.save(
            update_fields=(
                "status",
                "customer_return_tracking_number",
                "customer_return_tracking_submitted_at",
                "updated_at",
            )
        )

        edit_response = self.client.post(
            reverse("commerce_api:returns-tracking-submit", kwargs={"id": return_id}),
            {"tracking_number": "59 9999 1111 2222"},
            format="json",
            **self.auth,
        )
        self.assertEqual(edit_response.status_code, status.HTTP_200_OK)

        request_obj.refresh_from_db()
        self.assertEqual(request_obj.customer_return_tracking_number, "59999911112222")
        self.assertEqual(request_obj.customer_return_tracking_submitted_at, first_submit_at)
        self.assertEqual(request_obj.status, ReturnRequest.STATUS_IN_TRANSIT)

    def test_tracking_cannot_be_edited_after_one_hour_window(self):
        self._enable_returns()
        create_response = self.client.post(
            reverse("commerce_api:returns-create"),
            {
                "order_id": str(self.order.id),
                "reason_comment": "Need to return this item",
                "items": [{"order_item_id": str(self.order_item.id), "quantity": 1}],
            },
            format="json",
            **self.auth,
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        return_id = create_response.data["id"]

        request_obj = ReturnRequest.objects.get(id=return_id)
        request_obj.status = ReturnRequest.STATUS_IN_TRANSIT
        request_obj.customer_return_tracking_number = "59001541905785"
        request_obj.customer_return_tracking_submitted_at = timezone.now() - timedelta(hours=1, minutes=1)
        request_obj.save(
            update_fields=(
                "status",
                "customer_return_tracking_number",
                "customer_return_tracking_submitted_at",
                "updated_at",
            )
        )

        edit_response = self.client.post(
            reverse("commerce_api:returns-tracking-submit", kwargs={"id": return_id}),
            {"tracking_number": "59 9999 1111 2222"},
            format="json",
            **self.auth,
        )
        self.assertEqual(edit_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(edit_response.data["detail"], "Tracking number edit window has expired.")

    def test_eligible_orders_hides_order_when_all_quantities_already_returned(self):
        self._enable_returns()
        create_response = self.client.post(
            reverse("commerce_api:returns-create"),
            {
                "order_id": str(self.order.id),
                "reason_comment": "Need to return all items",
                "items": [{"order_item_id": str(self.order_item.id), "quantity": 2}],
            },
            format="json",
            **self.auth,
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        eligible_response = self.client.get(reverse("commerce_api:returns-eligible-orders"), **self.auth)
        self.assertEqual(eligible_response.status_code, status.HTTP_200_OK)
        self.assertEqual(eligible_response.data, [])
