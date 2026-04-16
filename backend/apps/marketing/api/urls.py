from django.urls import path

from apps.marketing.api.views import HeroSlideListAPIView, PromoBannerListAPIView

app_name = "marketing_api"

urlpatterns = [
    path("hero-slides/", HeroSlideListAPIView.as_view(), name="hero-slide-list"),
    path("promo-banners/", PromoBannerListAPIView.as_view(), name="promo-banner-list"),
]
