from rest_framework import serializers

from apps.users.models import User


class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "phone",
            "preferred_language",
            "is_staff",
            "is_superuser",
        )
