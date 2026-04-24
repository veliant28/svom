from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from apps.backoffice.api.serializers.hero_block_serializer import (
    BackofficeHeroBlockSettingsSerializer,
    BackofficeHeroSlideSerializer,
)
from apps.backoffice.api.views._base import BackofficeAPIView
from apps.marketing.models import HeroSlide
from apps.marketing.selectors import get_hero_slider_settings


class BackofficeHeroBlockSettingsAPIView(BackofficeAPIView):
    required_capability = "promo_banners.manage"

    def get(self, request):
        serializer = BackofficeHeroBlockSettingsSerializer(get_hero_slider_settings())
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        settings_obj = get_hero_slider_settings()
        serializer = BackofficeHeroBlockSettingsSerializer(settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class BackofficeHeroSlideListCreateAPIView(BackofficeAPIView):
    required_capability = "promo_banners.manage"

    def get(self, request):
        queryset = HeroSlide.objects.order_by("sort_order", "created_at")
        serializer = BackofficeHeroSlideSerializer(queryset, many=True, context={"request": request})
        return Response(
            {
                "count": len(serializer.data),
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        if HeroSlide.objects.count() >= 10:
            return Response(
                {"detail": "Можно хранить не более 10 hero-слайдов."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = BackofficeHeroSlideSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        output = BackofficeHeroSlideSerializer(instance, context={"request": request})
        return Response(output.data, status=status.HTTP_201_CREATED)


class BackofficeHeroSlideRetrieveUpdateDestroyAPIView(BackofficeAPIView):
    required_capability = "promo_banners.manage"

    def patch(self, request, id):
        instance = get_object_or_404(HeroSlide, id=id)
        serializer = BackofficeHeroSlideSerializer(
            instance,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        output = BackofficeHeroSlideSerializer(updated, context={"request": request})
        return Response(output.data, status=status.HTTP_200_OK)

    def delete(self, request, id):
        instance = get_object_or_404(HeroSlide, id=id)
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
