from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.marketing.models import FooterSettings, HeroSlide, HeroSliderSettings, PromoBanner, PromoBannerSettings


class MarketingAPISmokeTests(APITestCase):
    def setUp(self):
        HeroSliderSettings.objects.create(code="default", max_active_slides=10)
        PromoBannerSettings.objects.create(code="default", max_active_banners=5)
        FooterSettings.objects.create(code="default", working_hours="Mon-Sat 10:00-17:00", phone="+380998979467")

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
        hero_config_response = self.client.get(reverse("marketing_api:hero-slide-config"))
        promo_response = self.client.get(reverse("marketing_api:promo-banner-list"))
        promo_config_response = self.client.get(reverse("marketing_api:promo-banner-config"))
        footer_response = self.client.get(reverse("marketing_api:footer-settings"))

        self.assertEqual(hero_response.status_code, status.HTTP_200_OK)
        self.assertEqual(hero_config_response.status_code, status.HTTP_200_OK)
        self.assertEqual(promo_response.status_code, status.HTTP_200_OK)
        self.assertEqual(promo_config_response.status_code, status.HTTP_200_OK)
        self.assertEqual(footer_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(hero_response.data), 1)
        self.assertEqual(len(hero_config_response.data["slides"]), 1)
        self.assertEqual(hero_config_response.data["settings"]["transition_effect"], "crossfade")
        self.assertEqual(len(promo_response.data), 1)
        self.assertEqual(len(promo_config_response.data["banners"]), 1)
        self.assertEqual(promo_config_response.data["settings"]["transition_effect"], "fade")
        self.assertEqual(footer_response.data["working_hours"], "Mon-Sat 10:00-17:00")
        self.assertEqual(footer_response.data["phone"], "+380998979467")
