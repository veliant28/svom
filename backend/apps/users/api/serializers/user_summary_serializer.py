from rest_framework import serializers

from apps.users.models import User
from apps.users.rbac import get_backoffice_capabilities_for_user, get_user_system_role


class UserSummaryGroupSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class UserSummarySerializer(serializers.ModelSerializer):
    groups = serializers.SerializerMethodField()
    system_role = serializers.SerializerMethodField()
    backoffice_capabilities = serializers.SerializerMethodField()
    backoffice_capabilities_map = serializers.SerializerMethodField()
    has_backoffice_access = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "middle_name",
            "phone",
            "preferred_language",
            "is_staff",
            "is_superuser",
            "groups",
            "system_role",
            "backoffice_capabilities",
            "backoffice_capabilities_map",
            "has_backoffice_access",
        )

    def get_groups(self, obj: User):
        groups = obj.groups.order_by("name").values("id", "name")
        return UserSummaryGroupSerializer(groups, many=True).data

    def get_system_role(self, obj: User) -> str | None:
        return get_user_system_role(obj)

    def get_backoffice_capabilities(self, obj: User) -> list[str]:
        return sorted(get_backoffice_capabilities_for_user(obj))

    def get_backoffice_capabilities_map(self, obj: User) -> dict[str, bool]:
        return {code: True for code in self.get_backoffice_capabilities(obj)}

    def get_has_backoffice_access(self, obj: User) -> bool:
        return "backoffice.access" in get_backoffice_capabilities_for_user(obj)
