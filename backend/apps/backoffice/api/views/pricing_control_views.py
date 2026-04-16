from __future__ import annotations

from rest_framework.response import Response

from apps.backoffice.api.serializers.pricing_control_serializer import (
    PricingCategoryImpactQuerySerializer,
    PricingCategoryMarkupUpdateSerializer,
    PricingGlobalMarkupUpdateSerializer,
    PricingRecalculateSerializer,
)
from apps.backoffice.api.views._base import BackofficeAPIView
from apps.backoffice.selectors.pricing_control_selectors import (
    get_pricing_category_impact,
    get_pricing_control_panel_payload,
)
from apps.backoffice.services.pricing_control_service import PricingControlService


class PricingControlPanelAPIView(BackofficeAPIView):
    def get(self, request):
        return Response(get_pricing_control_panel_payload())


class PricingCategoryImpactAPIView(BackofficeAPIView):
    def get(self, request):
        serializer = PricingCategoryImpactQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        payload = get_pricing_category_impact(
            category_id=str(serializer.validated_data["category_id"]),
            include_children=serializer.validated_data["include_children"],
        )
        return Response(payload)


class PricingGlobalMarkupAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = PricingGlobalMarkupUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = PricingControlService()
        result = service.apply_global_markup(
            percent_markup=PricingControlService.normalize_percent_markup(serializer.validated_data["percent_markup"]),
            dispatch_async=serializer.validated_data["dispatch_async"],
        )
        return Response(
            {
                "mode": result.mode,
                "affected_products": result.affected_products,
                "created_policies": result.created_policies,
                "updated_policies": result.updated_policies,
                "markup_percent": result.markup_percent,
            }
        )


class PricingCategoryMarkupAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = PricingCategoryMarkupUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = PricingControlService()
        result = service.apply_category_markup(
            category_id=str(serializer.validated_data["category_id"]),
            percent_markup=PricingControlService.normalize_percent_markup(serializer.validated_data["percent_markup"]),
            include_children=serializer.validated_data["include_children"],
            dispatch_async=serializer.validated_data["dispatch_async"],
        )
        return Response(
            {
                "mode": result.mode,
                "affected_products": result.affected_products,
                "target_categories": result.target_categories,
                "created_policies": result.created_policies,
                "updated_policies": result.updated_policies,
                "markup_percent": result.markup_percent,
            }
        )


class PricingRecalculateAPIView(BackofficeAPIView):
    def post(self, request):
        serializer = PricingRecalculateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        category_id = serializer.validated_data.get("category_id")
        service = PricingControlService()
        result = service.recalculate(
            dispatch_async=serializer.validated_data["dispatch_async"],
            category_id=str(category_id) if category_id else None,
            include_children=serializer.validated_data["include_children"],
        )
        return Response(
            {
                "mode": result.mode,
                "affected_products": result.affected_products,
                "target_categories": result.target_categories,
            }
        )
