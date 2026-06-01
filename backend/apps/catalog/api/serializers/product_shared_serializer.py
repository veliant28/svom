from rest_framework import serializers

from apps.catalog.models import Category


class ProductCategorySerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "name", "slug")

    def _resolve_locale(self) -> str | None:
        if hasattr(self, "_resolved_locale"):
            return getattr(self, "_resolved_locale")
        request = self.context.get("request")
        if request is None:
            setattr(self, "_resolved_locale", None)
            return None

        locale = (request.query_params.get("locale") or "").strip()
        if locale:
            setattr(self, "_resolved_locale", locale)
            return locale

        language_code = getattr(request, "LANGUAGE_CODE", "")
        if language_code:
            resolved = str(language_code)
            setattr(self, "_resolved_locale", resolved)
            return resolved

        accept_language = str(request.headers.get("Accept-Language", "")).strip()
        if not accept_language:
            setattr(self, "_resolved_locale", None)
            return None
        resolved = accept_language.split(",", 1)[0]
        setattr(self, "_resolved_locale", resolved)
        return resolved

    def get_name(self, obj: Category) -> str:
        return obj.get_localized_name(self._resolve_locale())
