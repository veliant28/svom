from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.db.models.functions import Lower, Trim
from django.db.models.deletion import ProtectedError
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.backoffice.api.serializers import BackofficeCatalogCategorySerializer
from apps.backoffice.permissions import IsStaffOrSuperuser
from apps.catalog.models import Category


class BackofficeCatalogCategoryPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 500


class BackofficeCatalogCategoryListCreateAPIView(ListCreateAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = BackofficeCatalogCategorySerializer
    ordering = ("name",)
    pagination_class = BackofficeCatalogCategoryPagination

    def get_queryset(self):
        queryset = Category.objects.select_related("parent")
        query = self.request.query_params.get("q", "").strip()
        is_active = self.request.query_params.get("is_active", "").strip().lower()
        parent = self.request.query_params.get("parent", "").strip().lower()
        source = self.request.query_params.get("source", "").strip().lower()
        show_in_header = self.request.query_params.get("show_in_header", "").strip().lower()
        duplicates = self.request.query_params.get("duplicates", "").strip().lower()

        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(name_uk__icontains=query)
                | Q(name_ru__icontains=query)
                | Q(name_en__icontains=query),
            )
        if is_active in {"true", "1", "yes"}:
            queryset = queryset.filter(is_active=True)
        elif is_active in {"false", "0", "no"}:
            queryset = queryset.filter(is_active=False)

        if parent:
            if parent in {"null", "none", "root"}:
                queryset = queryset.filter(parent__isnull=True)
            else:
                queryset = queryset.filter(parent_id=parent)

        if source:
            queryset = queryset.filter(source=source)

        if show_in_header in {"true", "1", "yes"}:
            queryset = queryset.filter(show_in_header=True)
        elif show_in_header in {"false", "0", "no"}:
            queryset = queryset.filter(show_in_header=False)

        if duplicates in {"true", "1", "yes"}:
            duplicate_groups = list(
                Category.objects.annotate(
                    normalized_name=Lower(Trim("name")),
                )
                .values("source", "normalized_name")
                .annotate(total=Count("id"))
                .filter(total__gt=1)
            )
            duplicate_ids: list[str] = []
            for group in duplicate_groups:
                group_qs = Category.objects.annotate(normalized_name=Lower(Trim("name"))).filter(
                    source=group["source"],
                    normalized_name=group["normalized_name"],
                )
                duplicate_ids.extend(str(value) for value in group_qs.values_list("id", flat=True))
            queryset = queryset.filter(id__in=duplicate_ids)

        queryset = queryset.annotate(
            source_priority=Case(
                When(source=Category.SOURCE_MANUAL, then=Value(0)),
                When(source=Category.SOURCE_LEGACY, then=Value(1)),
                When(source=Category.SOURCE_IMPORT, then=Value(2)),
                When(source=Category.SOURCE_AUTODB_PRO, then=Value(3)),
                default=Value(4),
                output_field=IntegerField(),
            )
        ).order_by("-show_in_header", "source_priority", "name", "id")

        return queryset


class BackofficeCatalogCategoryRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = BackofficeCatalogCategorySerializer
    lookup_field = "id"

    def get_queryset(self):
        return Category.objects.select_related("parent").order_by("name")

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            linked_products = instance.products.count()
            linked_children = instance.children.count()
            detail = "Категорию нельзя удалить: есть связанные записи."
            if linked_products:
                detail = f"Категорию нельзя удалить: связанных товаров {linked_products}."
            elif linked_children:
                detail = f"Категорию нельзя удалить: есть дочерние категории ({linked_children})."

            return Response(
                {
                    "detail": detail,
                    "linked_products": linked_products,
                    "linked_children": linked_children,
                },
                status=status.HTTP_409_CONFLICT,
            )
