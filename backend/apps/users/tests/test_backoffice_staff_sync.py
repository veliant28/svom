from django.contrib.auth.models import Group
from django.test import TestCase

from apps.backoffice.api.serializers.backoffice_user_rbac_serializer import BackofficeUserUpdateSerializer
from apps.users.models import User
from apps.users.rbac import ensure_system_groups_exist, set_user_system_role


class BackofficeStaffSyncTests(TestCase):
    def setUp(self):
        ensure_system_groups_exist()
        self.user = User.objects.create_user(
            email="staff-sync@test.local",
            password="pass12345",
            first_name="Staff",
        )
        self.custom_group = Group.objects.create(name="Custom Non-System Group")
        self.operator_group = Group.objects.get(name="Backoffice Role: operator")
        self.user_group = Group.objects.get(name="Backoffice Role: user")

    def test_set_user_system_role_toggles_is_staff_for_backoffice_roles(self):
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)

        set_user_system_role(user=self.user, role_code="manager")
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_staff)

        set_user_system_role(user=self.user, role_code="operator")
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_staff)

        set_user_system_role(user=self.user, role_code="user")
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)

    def test_group_update_serializer_syncs_is_staff_by_system_groups(self):
        serializer = BackofficeUserUpdateSerializer(
            instance=self.user,
            data={"group_ids": [self.operator_group.id]},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_staff)

        serializer = BackofficeUserUpdateSerializer(
            instance=self.user,
            data={"group_ids": [self.custom_group.id]},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)
        self.assertEqual(list(self.user.groups.values_list("id", flat=True)), [self.custom_group.id])

        serializer = BackofficeUserUpdateSerializer(
            instance=self.user,
            data={"group_ids": []},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)
        self.assertIn(self.user_group, list(self.user.groups.all()))

    def test_direct_group_membership_change_syncs_is_staff(self):
        self.user.groups.set([self.operator_group])
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_staff)

        self.user.groups.set([self.custom_group])
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)

        self.user.groups.clear()
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)
