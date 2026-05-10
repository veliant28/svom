from django.db.models import Exists, OuterRef, Q
from django.db.models import Prefetch
from django.db.models.functions import Length
from django.db.models.deletion import ProtectedError
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.backoffice.api.serializers import BackofficeCatalogProductSerializer
from apps.backoffice.permissions import IsStaffOrSuperuser
from apps.catalog.models import AutoDbProductLinkQuality
from apps.catalog.models import Product
from apps.pricing.models import SupplierOffer
from apps.supplier_imports.models import SupplierRawOffer


class BackofficeCatalogProductPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 500


def _parse_bool_param(value: str) -> bool | None:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    return None


def _normalize_autodb_link_status(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized in {"", "all"}:
        return ""
    if normalized in {"linked", "unlinked", "trusted", "suspicious"}:
        return normalized
    if normalized in {"needs_review", "needs_manual_review"}:
        return "needs_review"
    return ""


class BackofficeCatalogProductListCreateAPIView(ListCreateAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = BackofficeCatalogProductSerializer
    ordering = ("name",)
    pagination_class = BackofficeCatalogProductPagination

    @staticmethod
    def _supplier_offers_prefetch() -> Prefetch:
        return Prefetch(
            "supplier_offers",
            queryset=SupplierOffer.objects.select_related("supplier").order_by("supplier__priority", "-updated_at", "id"),
            to_attr="backoffice_supplier_offers",
        )

    @staticmethod
    def _raw_offers_prefetch() -> Prefetch:
        return Prefetch(
            "raw_supplier_offers",
            queryset=SupplierRawOffer.objects.select_related("source", "supplier").order_by("supplier__priority", "source__code", "-updated_at", "-id"),
            to_attr="backoffice_raw_offers",
        )

    def get_queryset(self):
        queryset = (
            Product.objects.select_related("brand", "category", "product_price", "product_price__policy")
            .prefetch_related(self._supplier_offers_prefetch(), self._raw_offers_prefetch())
            .order_by("name")
        )
        query = self.request.query_params.get("q", "").strip()
        brand = self.request.query_params.get("brand", "").strip()
        category = self.request.query_params.get("category", "").strip()
        supplier_code = self.request.query_params.get("supplier", "").strip().lower()
        has_product_price = _parse_bool_param(self.request.query_params.get("has_product_price", ""))
        has_available_offer = _parse_bool_param(self.request.query_params.get("has_available_offer", ""))
        autodb_link_status = _normalize_autodb_link_status(self.request.query_params.get("autodb_link_status", ""))

        is_active = _parse_bool_param(self.request.query_params.get("is_active", ""))
        is_featured = _parse_bool_param(self.request.query_params.get("is_featured", ""))
        is_new = _parse_bool_param(self.request.query_params.get("is_new", ""))
        is_bestseller = _parse_bool_param(self.request.query_params.get("is_bestseller", ""))
        missing_autodb_link = _parse_bool_param(self.request.query_params.get("missing_autodb_link", ""))
        code_like_name = _parse_bool_param(self.request.query_params.get("code_like_name", ""))

        name_source = self.request.query_params.get("name_source", "").strip()
        name_translation_status = self.request.query_params.get("name_translation_status", "").strip()
        catalog_source = self.request.query_params.get("catalog_source", "").strip()
        needs_manual_mapping = _parse_bool_param(self.request.query_params.get("needs_manual_mapping", ""))

        if query:
            queryset = queryset.filter(
                Q(sku__icontains=query)
                | Q(article__icontains=query)
                | Q(name__icontains=query)
                | Q(slug__icontains=query)
                | Q(brand__name__icontains=query)
                | Q(display_brand_name__icontains=query)
                | Q(autodb_supplier_name__icontains=query)
                | Q(category__name__icontains=query),
            )
        if brand:
            if str(brand).isdigit():
                queryset = queryset.filter(autodb_supplier_id=int(brand))
            else:
                queryset = queryset.filter(brand_id=brand)
        if category:
            queryset = queryset.filter(category_id=category)
        if supplier_code and supplier_code != "all":
            queryset = queryset.filter(supplier_offers__supplier__code=supplier_code).distinct()
        if has_product_price is not None:
            queryset = queryset.filter(product_price__isnull=not has_product_price)
        if has_available_offer is not None:
            available_offer_exists = SupplierOffer.objects.filter(
                product_id=OuterRef("pk"),
                is_available=True,
            )
            queryset = queryset.annotate(_has_available_offer=Exists(available_offer_exists))
            queryset = queryset.filter(_has_available_offer=has_available_offer)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        if is_featured is not None:
            queryset = queryset.filter(is_featured=is_featured)
        if is_new is not None:
            queryset = queryset.filter(is_new=is_new)
        if is_bestseller is not None:
            queryset = queryset.filter(is_bestseller=is_bestseller)
        if name_source:
            queryset = queryset.filter(name_source=name_source)
        if name_translation_status:
            queryset = queryset.filter(name_translation_status=name_translation_status)
        if catalog_source:
            queryset = queryset.filter(catalog_source=catalog_source)
        if missing_autodb_link is not None:
            if missing_autodb_link:
                queryset = queryset.filter(Q(autodb_supplier_id__isnull=True) | Q(autodb_article_number=""))
            else:
                queryset = queryset.filter(autodb_supplier_id__isnull=False).exclude(autodb_article_number="")
        if code_like_name is not None:
            queryset = queryset.annotate(_name_len=Length("name"))
            code_like_q = Q(_name_len__lte=32) & ~Q(name__contains=" ")
            queryset = queryset.filter(code_like_q) if code_like_name else queryset.exclude(code_like_q)
        if needs_manual_mapping is not None:
            if needs_manual_mapping:
                queryset = queryset.filter(Q(catalog_source=Product.CATALOG_SOURCE_AUTODB_PRO) & (Q(autodb_supplier_id__isnull=True) | Q(autodb_article_number="")))
            else:
                queryset = queryset.exclude(
                    Q(catalog_source=Product.CATALOG_SOURCE_AUTODB_PRO) & (Q(autodb_supplier_id__isnull=True) | Q(autodb_article_number=""))
                )
        if autodb_link_status == "linked":
            queryset = queryset.filter(autodb_supplier_id__isnull=False).exclude(autodb_article_number="")
        elif autodb_link_status == "unlinked":
            queryset = queryset.filter(Q(autodb_supplier_id__isnull=True) | Q(autodb_article_number=""))
        elif autodb_link_status == "trusted":
            queryset = queryset.filter(
                autodb_link_qualities__status=AutoDbProductLinkQuality.STATUS_TRUSTED
            ).distinct()
        elif autodb_link_status == "suspicious":
            queryset = queryset.filter(
                autodb_link_qualities__status=AutoDbProductLinkQuality.STATUS_SUSPICIOUS
            ).distinct()
        elif autodb_link_status == "needs_review":
            queryset = queryset.filter(
                autodb_link_qualities__status=AutoDbProductLinkQuality.STATUS_NEEDS_MANUAL_REVIEW
            ).distinct()

        return queryset

    def _fallback_paginated_rows(self, queryset):
        paginator = getattr(self, "paginator", None)
        page = getattr(paginator, "page", None)
        if paginator is None or page is None:
            return []

        page_size = paginator.get_page_size(self.request) or paginator.page_size or 20
        page_number = int(getattr(page, "number", 1) or 1)
        if page_number < 1:
            page_number = 1

        start = (page_number - 1) * page_size
        stop = start + page_size
        page_ids = list(queryset.values_list("id", flat=True)[start:stop])
        if not page_ids:
            return []

        rows = (
            Product.objects.filter(id__in=page_ids)
            .select_related("brand", "category", "product_price", "product_price__policy")
            .prefetch_related(self._supplier_offers_prefetch(), self._raw_offers_prefetch())
        )
        by_id = {item.id: item for item in rows}
        return [by_id[item_id] for item_id in page_ids if item_id in by_id]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is None:
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)

        serializer = self.get_serializer(page, many=True)
        data = list(serializer.data)

        page_obj = getattr(getattr(self, "paginator", None), "page", None)
        total_count = int(getattr(getattr(page_obj, "paginator", None), "count", 0) or 0)
        if not data and total_count > 0:
            fallback_rows = self._fallback_paginated_rows(queryset)
            if fallback_rows:
                data = list(self.get_serializer(fallback_rows, many=True).data)

        return self.get_paginated_response(data)


class BackofficeCatalogProductRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    serializer_class = BackofficeCatalogProductSerializer
    lookup_field = "id"

    def get_queryset(self):
        supplier_offers_prefetch = Prefetch(
            "supplier_offers",
            queryset=SupplierOffer.objects.select_related("supplier").order_by("supplier__priority", "-updated_at", "id"),
            to_attr="backoffice_supplier_offers",
        )
        raw_offers_prefetch = Prefetch(
            "raw_supplier_offers",
            queryset=SupplierRawOffer.objects.select_related("source", "supplier").order_by("supplier__priority", "source__code", "-updated_at", "-id"),
            to_attr="backoffice_raw_offers",
        )
        return (
            Product.objects.select_related("brand", "category", "product_price", "product_price__policy")
            .prefetch_related(supplier_offers_prefetch, raw_offers_prefetch)
            .order_by("name")
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            detail = "Товар нельзя удалить: есть связанные записи."
            return Response({"detail": detail, "linked_product_id": str(instance.id)}, status=status.HTTP_409_CONFLICT)
