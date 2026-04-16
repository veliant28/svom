from __future__ import annotations

from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response

from apps.backoffice.api.serializers import (
    CategoryMappingCategoryOptionSerializer,
    SupplierRawOfferCategoryMappingDetailSerializer,
    SupplierRawOfferCategoryMappingUpdateSerializer,
)
from apps.backoffice.api.views._base import BackofficeAPIView
from apps.catalog.models import Category
from apps.supplier_imports.models import SupplierRawOffer
from apps.supplier_imports.services import SupplierRawOfferCategoryMappingService


class SupplierRawOfferCategoryMappingAPIView(BackofficeAPIView):
    def get(self, request, raw_offer_id):
        raw_offer = self._get_raw_offer(raw_offer_id=raw_offer_id)
        if raw_offer is None:
            return Response({"detail": "Raw offer not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = SupplierRawOfferCategoryMappingDetailSerializer(raw_offer, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, raw_offer_id):
        raw_offer = self._get_raw_offer(raw_offer_id=raw_offer_id)
        if raw_offer is None:
            return Response({"detail": "Raw offer not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = SupplierRawOfferCategoryMappingUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        category_id = serializer.validated_data["category_id"]
        category = Category.objects.filter(id=category_id, is_active=True).first()
        if category is None:
            return Response({"detail": "Category not found."}, status=status.HTTP_404_NOT_FOUND)

        SupplierRawOfferCategoryMappingService().apply_manual_mapping(
            raw_offer=raw_offer,
            category=category,
            actor=request.user,
        )
        raw_offer.refresh_from_db()
        response_serializer = SupplierRawOfferCategoryMappingDetailSerializer(raw_offer, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, raw_offer_id):
        raw_offer = self._get_raw_offer(raw_offer_id=raw_offer_id)
        if raw_offer is None:
            return Response({"detail": "Raw offer not found."}, status=status.HTTP_404_NOT_FOUND)

        SupplierRawOfferCategoryMappingService().clear_mapping(raw_offer=raw_offer, actor=request.user)
        raw_offer.refresh_from_db()
        serializer = SupplierRawOfferCategoryMappingDetailSerializer(raw_offer, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def _get_raw_offer(self, *, raw_offer_id) -> SupplierRawOffer | None:
        return (
            SupplierRawOffer.objects.select_related(
                "supplier",
                "mapped_category",
                "mapped_category__parent",
                "matched_product",
                "matched_product__category",
                "matched_product__category__parent",
            )
            .filter(id=raw_offer_id)
            .first()
        )


class CategoryMappingCategorySearchAPIView(BackofficeAPIView):
    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        locale = (request.query_params.get("locale") or "").strip().lower()
        page_size = self._parse_page_size(request.query_params.get("page_size"))

        queryset = Category.objects.filter(is_active=True).order_by("name")
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(name_uk__icontains=query)
                | Q(name_ru__icontains=query)
                | Q(name_en__icontains=query)
            )

        categories = list(queryset.select_related("parent")[:page_size])
        categories_by_id = {str(item.id): item for item in categories}
        pending_parent_ids = {str(item.parent_id) for item in categories if item.parent_id}
        while pending_parent_ids:
            parent_rows = list(Category.objects.filter(id__in=pending_parent_ids).select_related("parent"))
            pending_parent_ids = set()
            for parent in parent_rows:
                parent_id = str(parent.id)
                if parent_id in categories_by_id:
                    continue
                categories_by_id[parent_id] = parent
                if parent.parent_id and str(parent.parent_id) not in categories_by_id:
                    pending_parent_ids.add(str(parent.parent_id))

        child_parent_ids = {
            str(item)
            for item in Category.objects.filter(is_active=True, parent_id__in=[item.id for item in categories]).values_list(
                "parent_id", flat=True
            )
            if item
        }

        results = [
            {
                "id": category.id,
                "name": self._localized_name(category=category, locale=locale),
                "breadcrumb": self._breadcrumb(category=category, locale=locale, categories_by_id=categories_by_id),
                "is_leaf": str(category.id) not in child_parent_ids,
            }
            for category in categories
        ]

        serializer = CategoryMappingCategoryOptionSerializer(results, many=True)
        return Response(
            {
                "count": queryset.count(),
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def _parse_page_size(self, value: str | None) -> int:
        default = 20
        max_size = 100
        if not value:
            return default
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return max(1, min(max_size, parsed))

    def _localized_name(self, *, category: Category, locale: str) -> str:
        return category.get_localized_name(locale)

    def _breadcrumb(self, *, category: Category, locale: str, categories_by_id: dict[str, Category]) -> str:
        names: list[str] = []
        seen: set[str] = set()
        current = category
        while current is not None and str(current.id) not in seen:
            seen.add(str(current.id))
            names.append(self._localized_name(category=current, locale=locale))
            if not current.parent_id:
                break
            current = categories_by_id.get(str(current.parent_id))
        names.reverse()
        return " / ".join(item for item in names if item)
