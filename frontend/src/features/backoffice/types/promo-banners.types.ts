export type BackofficePromoBannerEffect =
  | "fade"
  | "slide_left"
  | "slide_up"
  | "blinds_vertical"
  | "zoom_in";

export type BackofficePromoBannerSettings = {
  autoplay_enabled: boolean;
  transition_interval_ms: number;
  transition_speed_ms: number;
  transition_effect: BackofficePromoBannerEffect;
  max_active_banners: number;
};

export type BackofficePromoBanner = {
  id: string;
  title: string;
  description: string;
  image: string;
  image_url: string;
  target_url: string;
  sort_order: number;
  is_active: boolean;
  starts_at: string | null;
  ends_at: string | null;
  created_at: string;
  updated_at: string;
};
