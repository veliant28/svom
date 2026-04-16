from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.marketing.models import HeroSlide, HeroSliderSettings, PromoBanner, PromoBannerSettings


class MarketingAPISmokeTests(APITestCase):
    def setUp(self):
        HeroSliderSettings.objects.create(code="default", max_active_slides=10)
        PromoBannerSettings.objects.create(code="default", max_active_banners=5)

        HeroSlide.objects.create(
            title_uk="Hero",
            title_en="Hero",
            subtitle_uk="Subtitle",
            subtitle_en="Subtitle",
            desktop_image="marketing/hero/desktop/test.png",
            mobile_image="marketing/hero/mobile/test.png",
            sort_order=1,
            is_active=True,
        )
        PromoBanner.objects.create(
            title_uk="Promo",
            title_en="Promo",
            description_uk="Description",
            description_en="Description",
            image="marketing/promo/test.png",
            sort_order=1,
            is_active=True,
        )

    def test_marketing_endpoints_return_data(self):
        hero_response = self.client.get(reverse("marketing_api:hero-slide-list"))
        promo_response = self.client.get(reverse("marketing_api:promo-banner-list"))

        self.assertEqual(hero_response.status_code, status.HTTP_200_OK)
        self.assertEqual(promo_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(hero_response.data), 1)
        self.assertEqual(len(promo_response.data), 1)
