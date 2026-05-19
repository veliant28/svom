export type IntegrationCenterToggleKey =
  | "payment.monobank"
  | "payment.novapay"
  | "payment.liqpay"
  | "payment.cash_on_delivery"
  | "delivery.pickup"
  | "delivery.nova_poshta"
  | "delivery.courier"
  | "supplier.utr"
  | "supplier.gpl"
  | "integration.vchasno_kasa"
  | "integration.seo"
  | "integration.email"
  | "integration.telegram"
  | "integration.telegram_ops"
  | "integration.telegram_support"
  | "integration.telegram_system"
  | "returns.enabled";

export type BackofficeIntegrationCenterState = Record<IntegrationCenterToggleKey, boolean>;

export type IntegrationTranslatorProvider = "google" | "libretranslate";

export type BackofficeIntegrationTranslatorState = {
  provider: IntegrationTranslatorProvider;
  google_api_key_masked: string;
  has_google_api_key: boolean;
};

export type BackofficeAutoDbRemoteState = {
  has_schema: boolean;
  remote_host: string;
  remote_port: number;
  remote_database: string;
  remote_user: string;
  remote_password: string;
  remote_user_masked: string;
  remote_password_masked: string;
  has_remote_user: boolean;
  has_remote_password: boolean;
  image_base_url: string;
};

export type BackofficeIntegrationCenterResponse = {
  state: BackofficeIntegrationCenterState;
  translator: BackofficeIntegrationTranslatorState;
  autodb_remote: BackofficeAutoDbRemoteState;
  returns: BackofficeReturnsSettingsState;
};

export type BackofficeReturnsSettingsState = {
  returns_enabled: boolean;
  returns_recipient_full_name: string;
  returns_recipient_phone: string;
  returns_region_ref: string;
  returns_region_label: string;
  returns_city_ref: string;
  returns_city_label: string;
  returns_np_warehouse_text: string;
  returns_non_returnable_category_ids: string[];
  returns_include_subcategories: boolean;
};
