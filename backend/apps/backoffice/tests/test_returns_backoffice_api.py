from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.catalog.models import Brand, Category, Product
from apps.commerce.models import Order, OrderItem, ReturnEvent, ReturnRequest
from apps.core.selectors import get_return_service_settings
from apps.users.models import User
from apps.users.rbac import set_user_system_role


class BackofficeReturnsApiTests(APITestCase):
    def setUp(self):
        self.manager = User.objects.create_user(email="returns-manager@test.local", password="pass12345")
        self.operator = User.objects.create_user(email="returns-operator@test.local", password="pass12345")
        set_user_system_role(user=self.manager, role_code="manager")
        set_user_system_role(user=self.operator, role_code="operator")

        self.manager_token = Token.objects.create(user=self.manager)
        self.operator_token = Token.objects.create(user=self.operator)
        self.manager_auth = {"HTTP_AUTHORIZATION": f"Token {self.manager_token.key}"}
        self.operator_auth = {"HTTP_AUTHORIZATION": f"Token {self.operator_token.key}"}

        self.customer = User.objects.create_user(email="returns-customer@test.local", password="pass12345")
        brand = Brand.objects.create(name="RET", slug="ret", is_active=True)
        category = Category.objects.create(name="Returns", slug="returns", is_active=True)
        product = Product.objects.create(
            sku="RET-BO-001",
            article="RET-BO-001",
            name="Return Product",
            slug="return-product",
            brand=brand,
            category=category,
            is_active=True,
        )

        order = Order.objects.create(
            user=self.customer,
            order_number="ORD-RET-BO-1",
            status=Order.STATUS_COMPLETED,
            contact_full_name="Customer",
            contact_phone="+380671112233",
            contact_email="returns-customer@test.local",
            delivery_method=Order.DELIVERY_NOVA_POSHTA,
            delivery_address="Kyiv",
            payment_method=Order.PAYMENT_CASH_ON_DELIVERY,
            subtotal="1000.00",
            total="1000.00",
            currency="UAH",
        )
        item = OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            product_sku=product.sku,
            quantity=1,
            unit_price="1000.00",
            line_total="1000.00",
        )

        self.return_request = ReturnRequest.objects.create(
            user=self.customer,
            order=order,
            return_number="RET-999998",
            status=ReturnRequest.STATUS_ACCEPTED,
            reason_comment="Need to return",
            refund_amount="1000.00",
            refund_status=ReturnRequest.REFUND_STATUS_PROCESSING,
        )
        self.return_request.items.create(
            order_item=item,
            product=product,
            product_name_snapshot=product.name,
            product_sku_snapshot=product.sku,
            quantity_ordered=1,
            quantity_requested=1,
            quantity_approved=1,
            original_unit_price="1000.00",
            original_line_total="1000.00",
            refund_amount="1000.00",
            is_returnable_snapshot=True,
        )

    def test_operator_cannot_mark_refunded(self):
        response = self.client.post(
            reverse("backoffice_api:returns-operational-status", kwargs={"id": self.return_request.id}),
            {"status": ReturnRequest.STATUS_REFUNDED},
            format="json",
            **self.operator_auth,
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_can_mark_refunded(self):
        response = self.client.post(
            reverse("backoffice_api:returns-operational-status", kwargs={"id": self.return_request.id}),
            {"status": ReturnRequest.STATUS_REFUNDED},
            format="json",
            **self.manager_auth,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.return_request.refresh_from_db()
        self.assertEqual(self.return_request.status, ReturnRequest.STATUS_REFUNDED)

    def test_approve_persists_return_address_snapshot(self):
        settings = get_return_service_settings()
        settings.returns_recipient_full_name = "Recipient Name"
        settings.returns_recipient_phone = "+380671112233"
        settings.returns_region_label = "Kyivska"
        settings.returns_city_label = "Kyiv"
        settings.returns_np_warehouse_text = "Branch 12"
        settings.save(
            update_fields=(
                "returns_recipient_full_name",
                "returns_recipient_phone",
                "returns_region_label",
                "returns_city_label",
                "returns_np_warehouse_text",
                "updated_at",
            )
        )

        self.return_request.status = ReturnRequest.STATUS_NEW
        self.return_request.save(update_fields=("status", "updated_at"))

        response = self.client.post(
            reverse("backoffice_api:returns-operational-status", kwargs={"id": self.return_request.id}),
            {"status": ReturnRequest.STATUS_APPROVED},
            format="json",
            **self.manager_auth,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.return_request.refresh_from_db()
        snapshot = self.return_request.return_address_snapshot or {}
        self.assertEqual(snapshot.get("recipient_full_name"), "Recipient Name")
        self.assertEqual(snapshot.get("region_label"), "Kyivska")
        self.assertEqual(snapshot.get("city_label"), "Kyiv")
        self.assertEqual(snapshot.get("np_warehouse_text"), "Branch 12")

    def test_admin_comment_can_be_saved_without_status_change(self):
        self.assertEqual(self.return_request.status, ReturnRequest.STATUS_ACCEPTED)

        response = self.client.post(
            reverse("backoffice_api:returns-operational-status", kwargs={"id": self.return_request.id}),
            {
                "status": ReturnRequest.STATUS_ACCEPTED,
                "admin_comment": "Проверьте упаковку перед отправкой.",
            },
            format="json",
            **self.manager_auth,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.return_request.refresh_from_db()
        self.assertEqual(self.return_request.admin_comment, "Проверьте упаковку перед отправкой.")
        self.assertEqual(self.return_request.status, ReturnRequest.STATUS_ACCEPTED)
        self.assertTrue(
            ReturnEvent.objects.filter(
                return_request=self.return_request,
                from_status=ReturnRequest.STATUS_ACCEPTED,
                to_status=ReturnRequest.STATUS_ACCEPTED,
                metadata__admin_comment_updated=True,
            ).exists()
        )
