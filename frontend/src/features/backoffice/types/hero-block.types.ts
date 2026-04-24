export type BackofficeHeroBlockEffect =
  | "crossfade"
  | "pan_left"
  | "lift_up"
  | "cinematic_zoom"
  | "reveal_right";

export type BackofficeHeroBlockSettings = {
  autoplay_enabled: boolean;
  transition_interval_ms: number;
  transition_speed_ms: number;
  transition_effect: BackofficeHeroBlockEffect;
  max_active_slides: number;
};

export type BackofficeHeroSlide = {
  id: string;
  title_uk: string;
  title_ru: string;
  title_en: string;
  subtitle_uk: string;
  subtitle_ru: string;
  subtitle_en: string;
  desktop_image: string;
  desktop_image_url: string;
  mobile_image: string;
  mobile_image_url: string;
  cta_url: string;
  sort_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};
