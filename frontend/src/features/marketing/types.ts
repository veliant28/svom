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

export type MarketingFooterSettings = {
  working_hours: string;
  phone: string;
};
