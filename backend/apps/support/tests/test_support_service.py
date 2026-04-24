from __future__ import annotations

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.support.models import SupportMessage, SupportThread
from apps.support.services.support_service import send_support_message
from apps.users.models import User


class SupportServiceSendMessageTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            email="support-customer@test.local",
            first_name="Customer",
            password="demo12345",
        )
        self.staff = User.objects.create_user(
            email="support-staff@test.local",
            first_name="Staff",
            password="demo12345",
            is_staff=True,
            is_superuser=True,
        )

    def test_staff_can_send_message_to_closed_thread(self):
        thread = SupportThread.objects.create(
            subject="Closed thread",
            customer=self.customer,
            status=SupportThread.STATUS_CLOSED,
        )

        messages = send_support_message(thread=thread, author=self.staff, body="Staff reply in closed thread")

        self.assertGreaterEqual(len(messages), 1)
        self.assertTrue(any(message.author_side == SupportMessage.SIDE_STAFF for message in messages))
        thread.refresh_from_db()
        self.assertEqual(thread.assigned_staff_id, self.staff.id)
        self.assertEqual(thread.status, SupportThread.STATUS_OPEN)

    def test_customer_cannot_send_message_to_closed_thread(self):
        thread = SupportThread.objects.create(
            subject="Closed thread",
            customer=self.customer,
            status=SupportThread.STATUS_CLOSED,
        )

        with self.assertRaises(ValidationError):
            send_support_message(thread=thread, author=self.customer, body="Customer reply in closed thread")
