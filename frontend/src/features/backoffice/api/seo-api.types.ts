export type SeoLocale = "uk" | "ru" | "en";
export type SeoEntityType = "product" | "category" | "brand" | "page";

export type BackofficeSeoSettings = {
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
  sitemap_last_rebuild_at: string | null;
  robots_txt: string;
  updated_at: string;
};

export type BackofficeSeoMetaTemplate = {
  id: string;
  entity_type: SeoEntityType;
  locale: SeoLocale;
  title_template: string;
  description_template: string;
  h1_template: string;
  og_title_template: string;
  og_description_template: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type BackofficeSeoMetaOverride = {
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
  created_at: string;
  updated_at: string;
};

export type BackofficeGoogleSettings = {
  is_enabled: boolean;
  ga4_measurement_id: string;
  gtm_container_id: string;
  search_console_verification_token: string;
  google_site_verification_meta: string;
  consent_mode_enabled: boolean;
  ecommerce_events_enabled: boolean;
  debug_mode: boolean;
  anonymize_ip: boolean;
  updated_at: string;
};

export type BackofficeGoogleEventSetting = {
  id: string;
  event_name: string;
  label: string;
  is_enabled: boolean;
  description: string;
  updated_at: string;
};

export type BackofficeGoogleSettingsPayload = {
  settings: BackofficeGoogleSettings;
  events: BackofficeGoogleEventSetting[];
};

export type BackofficeSeoDashboardHealthItem = {
  entity: string;
  label: string;
  total: number;
  missing_title: number;
  missing_description: number;
  ok: number;
};

export type BackofficeSeoDashboardMissingMetaItem = {
  entity: string;
  missing_title: number;
  missing_description: number;
};

export type BackofficeSeoDashboardGoogleEventState = {
  event_name: string;
  label: string;
  enabled: boolean;
};

export type BackofficeSeoDashboard = {
  products_count: number;
  categories_count: number;
  brands_count: number;
  active_overrides_count: number;
  active_templates_count: number;
  sitemap_enabled: boolean;
  google_enabled: boolean;
  ga4_configured: boolean;
  gtm_configured: boolean;
  search_console_configured: boolean;
  missing_meta_available: boolean;
  seo_health_by_entity: BackofficeSeoDashboardHealthItem[];
  missing_meta_by_type: BackofficeSeoDashboardMissingMetaItem[];
  google_events_state: BackofficeSeoDashboardGoogleEventState[];
  templates_by_entity: Array<{ entity_type: string; total: number }>;
};

export type BackofficeSeoSitemapRebuildResponse = {
  rebuild_started: boolean;
  sitemap_url: string;
  sitemap_enabled: boolean;
  product_sitemap_enabled: boolean;
  category_sitemap_enabled: boolean;
  brand_sitemap_enabled: boolean;
  products_count: number;
  categories_count: number;
  brands_count: number;
  rebuilt_at: string | null;
};

export type BackofficeSeoRobotsPreview = {
  robots_txt: string;
};

export type BackofficeSeoListResponse<T> = {
  count: number;
  results: T[];
};
