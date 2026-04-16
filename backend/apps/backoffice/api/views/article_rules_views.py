from django.db.models import Q
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated

from apps.backoffice.api.serializers import ArticleNormalizationRuleSerializer
from apps.backoffice.permissions import IsStaffOrSuperuser
from apps.backoffice.selectors import get_article_normalization_rules_queryset


class ArticleRuleListCreateAPIView(ListCreateAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = ArticleNormalizationRuleSerializer
    ordering = ("-priority", "name")

    def get_queryset(self):
        queryset = get_article_normalization_rules_queryset()
        query = self.request.query_params.get("q", "").strip()
        source_code = self.request.query_params.get("source", "").strip()
        rule_type = self.request.query_params.get("rule_type", "").strip()
        is_active = self.request.query_params.get("is_active", "").strip().lower()

        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(pattern__icontains=query) | Q(notes__icontains=query))
        if source_code:
            queryset = queryset.filter(source__code=source_code)
        if rule_type:
            queryset = queryset.filter(rule_type=rule_type)
        if is_active in {"true", "1", "yes"}:
            queryset = queryset.filter(is_active=True)
        elif is_active in {"false", "0", "no"}:
            queryset = queryset.filter(is_active=False)
        return queryset


class ArticleRuleRetrieveUpdateAPIView(RetrieveUpdateAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = ArticleNormalizationRuleSerializer
    lookup_field = "id"

    def get_queryset(self):
        return get_article_normalization_rules_queryset()
