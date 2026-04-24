export type BackofficeOrderReceiptSummary = {
  provider: string;
  available: boolean;
  status_code: number | null;
  status_key: string;
  status_label: string;
  check_fn: string;
  can_issue: boolean;
  can_open: boolean;
  can_sync: boolean;
  error_message: string;
};

export type BackofficeVchasnoKasaSettings = {
  is_enabled: boolean;
  api_token_masked: string;
  rro_fn: string;
  default_payment_type: number;
  default_tax_group: string;
  auto_issue_on_completed: boolean;
  send_customer_email: boolean;
  last_connection_checked_at: string | null;
  last_connection_ok: boolean | null;
  last_connection_message: string;
};

export type BackofficeVchasnoKasaConnectionCheck = {
  ok: boolean;
  message: string;
};

export type BackofficeVchasnoReceiptRow = {
  id: string;
  order_id: string;
  order_number: string;
  customer_name: string;
  amount: string;
  currency: string;
  status_code: number | null;
  status_key: string;
  status_label: string;
  check_fn: string;
  receipt_url: string;
  pdf_url: string;
  created_at: string;
  updated_at: string;
};

export type BackofficeVchasnoReceiptList = {
  count: number;
  results: BackofficeVchasnoReceiptRow[];
};

export type BackofficeOrderReceiptActionResult = {
  receipt: BackofficeOrderReceiptSummary;
  already_exists: boolean;
  sync_performed: boolean;
};
