from django.urls import path

from apps.marketing.api.views import HeroSlideConfigAPIView, HeroSlideListAPIView, PromoBannerConfigAPIView, PromoBannerListAPIView
from apps.marketing.api.views.footer_settings_view import FooterSettingsAPIView

app_name = "marketing_api"

urlpatterns = [
    path("hero-slides/", HeroSlideListAPIView.as_view(), name="hero-slide-list"),
    path("hero-slides/config/", HeroSlideConfigAPIView.as_view(), name="hero-slide-config"),
    path("promo-banners/", PromoBannerListAPIView.as_view(), name="promo-banner-list"),
    path("promo-banners/config/", PromoBannerConfigAPIView.as_view(), name="promo-banner-config"),
    path("footer-settings/", FooterSettingsAPIView.as_view(), name="footer-settings"),
]
