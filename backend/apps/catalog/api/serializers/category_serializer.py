from rest_framework import serializers

from apps.catalog.models import Category


class CategoryListSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    parent = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "parent")

    def _resolve_locale(self) -> str | None:
        request = self.context.get("request")
        if request is None:
            return None

        locale = (request.query_params.get("locale") or "").strip()
        if locale:
            return locale

        language_code = getattr(request, "LANGUAGE_CODE", "")
        if language_code:
            return str(language_code)

        accept_language = str(request.headers.get("Accept-Language", "")).strip()
        if not accept_language:
            return None
        return accept_language.split(",", 1)[0]

    def get_name(self, obj: Category) -> str:
        return obj.get_localized_name(self._resolve_locale())

    def get_parent(self, obj: Category) -> dict | None:
        if obj.parent is None:
            return None
        locale = self._resolve_locale()
        return {
            "id": str(obj.parent.id),
            "name": obj.parent.get_localized_name(locale),
            "slug": obj.parent.slug,
        }
