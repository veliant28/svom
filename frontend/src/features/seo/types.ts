export type SeoLocale = "uk" | "ru" | "en";
export type SeoEntityType = "product" | "category" | "brand" | "page";

export type SeoPublicSiteSettings = {
  is_enabled: boolean;
  default_meta_title_uk: string;
  default_meta_title_ru: string;
  default_meta_title_en: string;
  default_meta_description_uk: string;
  default_meta_description_ru: string;
  default_meta_description_en: string;
  default_og_title_uk: string;
  default_og_title_ru: string;
  default_og_title_en: string;
  default_og_description_uk: string;
  default_og_description_ru: string;
  default_og_description_en: string;
  default_robots_directive: string;
  canonical_base_url: string;
  sitemap_enabled: boolean;
  product_sitemap_enabled: boolean;
  category_sitemap_enabled: boolean;
  brand_sitemap_enabled: boolean;
  robots_txt: string;
};

export type SeoPublicGoogleSettings = {
  is_enabled: boolean;
  ga4_measurement_id: string;
  gtm_container_id: string;
  search_console_verification_token: string;
  google_site_verification_meta: string;
  consent_mode_enabled: boolean;
  ecommerce_events_enabled: boolean;
  debug_mode: boolean;
  anonymize_ip: boolean;
};

export type SeoPublicMetaTemplate = {
  id: string;
  entity_type: SeoEntityType;
  locale: SeoLocale;
  title_template: string;
  description_template: string;
  h1_template: string;
  og_title_template: string;
  og_description_template: string;
  is_active: boolean;
};

export type SeoPublicMetaOverride = {
  id: string;
  path: string;
  locale: SeoLocale;
  meta_title: string;
  meta_description: string;
  h1: string;
  canonical_url: string;
  robots_directive: string;
  og_title: string;
  og_description: string;
  og_image_url: string;
  is_active: boolean;
};

export type SeoPublicConfig = {
  settings: SeoPublicSiteSettings;
  google: SeoPublicGoogleSettings;
  events: Array<{
    id: string;
    event_name: string;
    label: string;
    is_enabled: boolean;
    description: string;
  }>;
  templates: SeoPublicMetaTemplate[];
  overrides: SeoPublicMetaOverride[];
};
