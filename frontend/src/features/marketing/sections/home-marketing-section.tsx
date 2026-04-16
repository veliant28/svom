"use client";

import { useLocale } from "next-intl";

import { HeroBackgroundSlider } from "@/features/marketing/components/hero-background-slider";
import { PromoBannerCarousel } from "@/features/marketing/components/promo-banner-carousel";
import { useHeroSlides } from "@/features/marketing/hooks/use-hero-slides";
import { usePromoBanners } from "@/features/marketing/hooks/use-promo-banners";

export function HomeMarketingSection() {
  const locale = useLocale();
  const { slides } = useHeroSlides(locale);
  const { banners } = usePromoBanners(locale);

  return (
    <>
      <HeroBackgroundSlider slides={slides} />
      <PromoBannerCarousel banners={banners} />
    </>
  );
}
