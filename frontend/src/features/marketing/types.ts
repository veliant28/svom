export type HeroSlide = {
  id: string;
  title: string;
  subtitle: string;
  desktop_image_url: string;
  mobile_image_url: string;
  cta_url: string;
  sort_order: number;
};

export type PromoBanner = {
  id: string;
  title: string;
  description: string;
  image_url: string;
  target_url: string;
  sort_order: number;
};

export type PromoBannerEffect =
  | "fade"
  | "slide_left"
  | "slide_up"
  | "blinds_vertical"
  | "zoom_in";

export type PromoBannerSettings = {
  autoplay_enabled: boolean;
  transition_interval_ms: number;
  transition_speed_ms: number;
  transition_effect: PromoBannerEffect;
  max_active_banners: number;
};

export type PromoBannerConfig = {
  settings: PromoBannerSettings;
  banners: PromoBanner[];
};

export type MarketingFooterSettings = {
  working_hours: string;
  phone: string;
};
