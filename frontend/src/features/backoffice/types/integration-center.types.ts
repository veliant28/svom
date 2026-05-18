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
  | "integration.telegram_system";

export type BackofficeIntegrationCenterState = Record<IntegrationCenterToggleKey, boolean>;

export type IntegrationTranslatorProvider = "google" | "libretranslate";

export type BackofficeIntegrationTranslatorState = {
  provider: IntegrationTranslatorProvider;
  google_api_key_masked: string;
  has_google_api_key: boolean;
};

export type BackofficeIntegrationCenterResponse = {
  state: BackofficeIntegrationCenterState;
  translator: BackofficeIntegrationTranslatorState;
};
