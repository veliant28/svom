from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.catalog.models import Brand, Category, Product
from apps.commerce.models import Order, OrderItem
from apps.pricing.models import ProductPrice, Supplier, SupplierOffer
from apps.users.models import User
from apps.users.rbac import set_user_system_role


class BackofficeOrderOperationsAPISmokeTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="ops-orders@test.local",
            first_name="ops-orders",
            password="demo12345",
            is_staff=True,
            is_superuser=True,
        )
        self.token = Token.objects.create(user=self.staff)
        self.auth = {"HTTP_AUTHORIZATION": f"Token {self.token.key}"}

        self.customer = User.objects.create_user(
            email="orders-customer@test.local",
            first_name="orders-customer",
            password="demo12345",
        )

        brand = Brand.objects.create(name="Order Brand", slug="order-brand", is_active=True)
        category = Category.objects.create(name="Order Category", slug="order-category", is_active=True)
        self.product = Product.objects.create(
            sku="ORD-001",
            article="ORD-001",
            name="Order Product",
            slug="order-product",
            brand=brand,
            category=category,
            is_active=True,
        )
        ProductPrice.objects.create(product=self.product, final_price="210.00", currency="UAH")

        self.supplier_a = Supplier.objects.create(name="Order Supplier A", code="ord-sup-a", is_active=True, is_preferred=True, priority=1)
        self.supplier_b = Supplier.objects.create(name="Order Supplier B", code="ord-sup-b", is_active=True, priority=2)

        self.offer_a = SupplierOffer.objects.create(
            supplier=self.supplier_a,
            product=self.product,
            supplier_sku="ORD-A",
            purchase_price="130.00",
            stock_qty=10,
            lead_time_days=0,
            is_available=True,
        )
        self.offer_b = SupplierOffer.objects.create(
            supplier=self.supplier_b,
            product=self.product,
            supplier_sku="ORD-B",
            purchase_price="120.00",
            stock_qty=4,
            lead_time_days=1,
            is_available=True,
        )

        self.order = Order.objects.create(
            user=self.customer,
            order_number="ORD-1001",
            status=Order.STATUS_NEW,
            contact_full_name="Order Customer",
            contact_phone="+380000000000",
            contact_email="orders-customer@test.local",
            delivery_method=Order.DELIVERY_PICKUP,
            payment_method=Order.PAYMENT_CASH_ON_DELIVERY,
            subtotal="210.00",
            delivery_fee="0.00",
            total="210.00",
            currency="UAH",
        )
        self.item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            product_sku=self.product.sku,
            quantity=2,
            unit_price="210.00",
            line_total="420.00",
            procurement_status=OrderItem.PROCUREMENT_PENDING,
            recommended_supplier_offer=self.offer_a,
            snapshot_availability_status="in_stock",
            snapshot_availability_label="In stock",
            snapshot_procurement_source="Ready from local warehouse",
            snapshot_currency="UAH",
            snapshot_sell_price="210.00",
        )

    def test_order_operations_and_procurement_endpoints(self):
        list_response = self.client.get(reverse("backoffice_api:order-operational-list"), **self.auth)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["count"], 1)

        detail_response = self.client.get(
            reverse("backoffice_api:order-operational-detail", kwargs={"id": str(self.order.id)}),
            **self.auth,
        )
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["order_number"], self.order.order_number)

        confirm_response = self.client.post(
            reverse("backoffice_api:order-action-confirm"),
            {"order_id": str(self.order.id)},
            format="json",
            **self.auth,
        )
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_PROCESSING)

        awaiting_response = self.client.post(
            reverse("backoffice_api:order-action-awaiting-procurement"),
            {"order_id": str(self.order.id)},
            format="json",
            **self.auth,
        )
        self.assertEqual(awaiting_response.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_PROCESSING)

        suggestions_response = self.client.get(reverse("backoffice_api:procurement-suggestions-list"), **self.auth)
        self.assertEqual(suggestions_response.status_code, status.HTTP_200_OK)
        self.assertIn("groups", suggestions_response.data)

        recommendation_response = self.client.get(
            reverse("backoffice_api:order-item-supplier-recommendation", kwargs={"item_id": str(self.item.id)}),
            **self.auth,
        )
        self.assertEqual(recommendation_response.status_code, status.HTTP_200_OK)
        self.assertIn("recommended_offer", recommendation_response.data)

        override_response = self.client.post(
            reverse("backoffice_api:order-item-supplier-override", kwargs={"item_id": str(self.item.id)}),
            {"supplier_offer_id": str(self.offer_b.id)},
            format="json",
            **self.auth,
        )
        self.assertEqual(override_response.status_code, status.HTTP_200_OK)
        self.item.refresh_from_db()
        self.assertEqual(self.item.selected_supplier_offer_id, self.offer_b.id)

        reserve_response = self.client.post(
            reverse("backoffice_api:order-action-reserve"),
            {"order_id": str(self.order.id)},
            format="json",
            **self.auth,
        )
        self.assertEqual(reserve_response.status_code, status.HTTP_200_OK)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_PROCESSING)

        ready_response = self.client.post(
            reverse("backoffice_api:order-action-ready-to-ship"),
            {"order_id": str(self.order.id)},
            format="json",
            **self.auth,
        )
        self.assertEqual(ready_response.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_READY_FOR_SHIPMENT)

        shipped_response = self.client.post(
            reverse("backoffice_api:order-action-ship"),
            {"order_id": str(self.order.id)},
            format="json",
            **self.auth,
        )
        self.assertEqual(shipped_response.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_SHIPPED)

        completed_response = self.client.post(
            reverse("backoffice_api:order-action-complete"),
            {"order_id": str(self.order.id)},
            format="json",
            **self.auth,
        )
        self.assertEqual(completed_response.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_COMPLETED)

    def test_only_administrator_and_manager_can_reset_order_to_new(self):
        manager = User.objects.create_user(
            email="ops-manager@test.local",
            first_name="ops-manager",
            password="demo12345",
        )
        operator = User.objects.create_user(
            email="ops-operator@test.local",
            first_name="ops-operator",
            password="demo12345",
        )
        superuser_without_group = User.objects.create_user(
            email="ops-super@test.local",
            first_name="ops-super",
            password="demo12345",
            is_staff=True,
            is_superuser=True,
        )
        set_user_system_role(user=manager, role_code="manager")
        set_user_system_role(user=operator, role_code="operator")

        manager_token = Token.objects.create(user=manager)
        operator_token = Token.objects.create(user=operator)
        superuser_token = Token.objects.create(user=superuser_without_group)
        manager_auth = {"HTTP_AUTHORIZATION": f"Token {manager_token.key}"}
        operator_auth = {"HTTP_AUTHORIZATION": f"Token {operator_token.key}"}
        superuser_auth = {"HTTP_AUTHORIZATION": f"Token {superuser_token.key}"}

        self.order.status = Order.STATUS_SHIPPED
        self.order.cancellation_reason_code = "supplier_shortage"
        self.order.cancellation_reason_note = "legacy note"
        self.order.save(update_fields=("status", "cancellation_reason_code", "cancellation_reason_note", "updated_at"))

        operator_response = self.client.post(
            reverse("backoffice_api:order-action-reset-to-new"),
            {"order_id": str(self.order.id)},
            format="json",
            **operator_auth,
        )
        self.assertEqual(operator_response.status_code, status.HTTP_403_FORBIDDEN)

        superuser_response = self.client.post(
            reverse("backoffice_api:order-action-reset-to-new"),
            {"order_id": str(self.order.id)},
            format="json",
            **superuser_auth,
        )
        self.assertEqual(superuser_response.status_code, status.HTTP_403_FORBIDDEN)

        manager_response = self.client.post(
            reverse("backoffice_api:order-action-reset-to-new"),
            {"order_id": str(self.order.id)},
            format="json",
            **manager_auth,
        )
        self.assertEqual(manager_response.status_code, status.HTTP_200_OK)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_NEW)
        self.assertEqual(self.order.cancellation_reason_code, "")
        self.assertEqual(self.order.cancellation_reason_note, "")
