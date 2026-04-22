from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from apps.users.rbac import sync_user_staff_flag_by_system_role


User = get_user_model()


@receiver(m2m_changed, sender=User.groups.through)
def sync_is_staff_on_group_membership_change(sender, instance, action: str, reverse: bool, pk_set, **kwargs) -> None:
    if action not in {"post_add", "post_remove", "post_clear"}:
        return

    if not reverse:
        sync_user_staff_flag_by_system_role(user=instance)
        return

    if action in {"post_add", "post_remove"} and pk_set:
        for user in User.objects.filter(pk__in=pk_set):
            sync_user_staff_flag_by_system_role(user=user)
