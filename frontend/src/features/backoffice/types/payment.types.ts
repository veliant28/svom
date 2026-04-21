export type BackofficeMonobankSettings = {
  is_enabled: boolean;
  merchant_token_masked: string;
  widget_key_id: string;
  widget_private_key_masked: string;
  webhook_url: string;
  redirect_url: string;
  last_connection_checked_at: string | null;
  last_connection_ok: boolean | null;
  last_connection_message: string;
  last_currency_sync_at: string | null;
};

export type BackofficeNovaPaySettings = {
  is_enabled: boolean;
  merchant_id: string;
  api_token_masked: string;
  last_connection_checked_at: string | null;
  last_connection_ok: boolean | null;
  last_connection_message: string;
};

export type BackofficeLiqPaySettings = {
  is_enabled: boolean;
  public_key_masked: string;
  private_key_masked: string;
  server_url: string;
  result_url: string;
  last_connection_checked_at: string | null;
  last_connection_ok: boolean | null;
  last_connection_message: string;
};

export type BackofficeMonobankConnectionCheck = {
  ok: boolean;
  message: string;
  public_key: string;
};

export type BackofficePaymentConnectionCheck = {
  ok: boolean;
  message: string;
};

export type BackofficeMonobankCurrencyRow = {
  pair: string;
  currency_code_a: number;
  currency_code_b: number;
  rate_buy: number | null;
  rate_sell: number | null;
  rate_cross: number | null;
  updated_at: string;
};

export type BackofficeMonobankCurrencyResponse = {
  rows: BackofficeMonobankCurrencyRow[];
  last_fetched_at: string | null;
};
