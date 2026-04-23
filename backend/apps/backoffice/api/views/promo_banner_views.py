from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from apps.backoffice.api.serializers.promo_banner_serializer import (
    BackofficePromoBannerSerializer,
    BackofficePromoBannerSettingsSerializer,
)
from apps.backoffice.api.views._base import BackofficeAPIView
from apps.marketing.models import PromoBanner
from apps.marketing.selectors import get_promo_banner_settings


class BackofficePromoBannerSettingsAPIView(BackofficeAPIView):
    required_capability = "promo_banners.manage"

    def get(self, request):
        serializer = BackofficePromoBannerSettingsSerializer(get_promo_banner_settings())
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        settings_obj = get_promo_banner_settings()
        serializer = BackofficePromoBannerSettingsSerializer(settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class BackofficePromoBannerListCreateAPIView(BackofficeAPIView):
    required_capability = "promo_banners.manage"

    def get(self, request):
        queryset = PromoBanner.objects.order_by("sort_order", "created_at")
        serializer = BackofficePromoBannerSerializer(queryset, many=True, context={"request": request})
        return Response(
            {
                "count": len(serializer.data),
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        if PromoBanner.objects.count() >= 10:
            return Response(
                {"detail": "Можно хранить не более 10 баннеров."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = BackofficePromoBannerSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        output = BackofficePromoBannerSerializer(instance, context={"request": request})
        return Response(output.data, status=status.HTTP_201_CREATED)


class BackofficePromoBannerRetrieveUpdateDestroyAPIView(BackofficeAPIView):
    required_capability = "promo_banners.manage"

    def patch(self, request, id):
        instance = get_object_or_404(PromoBanner, id=id)
        serializer = BackofficePromoBannerSerializer(
            instance,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        output = BackofficePromoBannerSerializer(updated, context={"request": request})
        return Response(output.data, status=status.HTTP_200_OK)

    def delete(self, request, id):
        instance = get_object_or_404(PromoBanner, id=id)
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
