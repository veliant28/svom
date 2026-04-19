export type BackofficeSupplierOffer = {
  id: string;
  supplier: string;
  supplier_code: string;
  supplier_name: string;
  supplier_sku: string;
  product_id: string;
  product_name: string;
  product_sku: string;
  product_article: string;
  brand_name: string;
  currency: string;
  purchase_price: string;
  logistics_cost: string;
  extra_cost: string;
  stock_qty: number;
  lead_time_days: number;
  is_available: boolean;
  created_at: string;
  updated_at: string;
};

export type BackofficeSupplierPublishMappedResult = {
  supplier_code: string;
  supplier_name: string;
  raw_rows_scanned: number;
  unique_latest_rows: number;
  eligible_rows: number;
  created_rows: number;
  updated_rows: number;
  skipped_rows: number;
  error_rows: number;
  products_created: number;
  products_updated: number;
  offers_created: number;
  offers_updated: number;
  raw_offer_links_updated: number;
  repriced_products: number;
  repricing_stats: Record<string, number>;
  skip_reasons: Record<string, number>;
  error_reasons: Record<string, number>;
};

export type BackofficeSupplierListItem = {
  code: "utr" | "gpl" | string;
  name: string;
  supplier_name: string;
  is_enabled: boolean;
  connection_status: string;
  last_successful_import_at: string | null;
  last_failed_import_at: string | null;
  can_run_now: boolean;
  cooldown_wait_seconds: number;
};

export type BackofficeSupplierWorkspace = {
  supplier: {
    code: string;
    name: string;
    supplier_name: string;
    is_enabled: boolean;
  };
  connection: {
    login: string;
    has_password: boolean;
    access_token_masked: string;
    refresh_token_masked: string;
    access_token_expires_at: string | null;
    refresh_token_expires_at: string | null;
    token_obtained_at: string | null;
    last_token_refresh_at: string | null;
    last_token_error_at: string | null;
    last_token_error_message: string;
    credentials_updated_at: string | null;
    status: string;
    last_connection_check_at: string | null;
    last_connection_status: string;
  };
  import: {
    last_run_status: string;
    last_run_at: string | null;
    last_successful_import_at: string | null;
    last_failed_import_at: string | null;
    last_import_error_message: string;
    last_run_summary: Record<string, unknown>;
    last_run_processed_rows: number;
    last_run_errors_count: number;
  };
  cooldown: {
    last_request_at: string | null;
    next_allowed_request_at: string | null;
    can_run: boolean;
    wait_seconds: number;
    cooldown_seconds: number;
    status_label: string;
  };
  utr: {
    available: boolean;
    last_brands_import_at: string | null;
    last_brands_import_count: number;
    last_brands_import_error_at: string | null;
    last_brands_import_error_message: string;
  };
};

export type BackofficeSupplierPriceList = {
  id: string;
  supplier_code: string;
  supplier_name: string;
  status: "generating" | "ready" | "downloaded" | "imported" | "failed" | string;
  remote_status: string;
  request_mode: string;
  requested_at: string | null;
  expected_ready_at: string | null;
  generated_at: string | null;
  downloaded_at: string | null;
  imported_at: string | null;
  imported_run_id: string | null;
  requested_format: string;
  original_format: string;
  locale: string;
  is_in_stock: boolean;
  show_scancode: boolean;
  utr_article: boolean;
  visible_brands: Array<number | string>;
  categories: string[];
  models_filter: string[];
  remote_id: string;
  source_file_name: string;
  source_file_path: string;
  downloaded_file_path: string;
  file_size_label: string;
  file_size_bytes: number;
  row_count: number;
  price_columns: string[];
  warehouse_columns: string[];
  has_multiple_prices: boolean;
  has_warehouses: boolean;
  generation_wait_seconds: number;
  download_available: boolean;
  import_available: boolean;
  last_error_at: string | null;
  last_error_message: string;
  cooldown_wait_seconds: number;
  created_at: string;
  updated_at: string;
};

export type BackofficeSupplierPriceListParams = {
  supplier_code: string;
  source: "utr_api" | "gpl_api" | "fallback" | string;
  formats: string[];
  format_options: Array<{
    format: string;
    caption: string;
  }>;
  supports: {
    in_stock: boolean;
    show_scancode: boolean;
    utr_article: boolean;
  };
  filter_rule: "one_of_three" | "none" | string;
  defaults: {
    format: string;
    in_stock: boolean;
    show_scancode: boolean;
    utr_article: boolean;
  };
  visible_brands_count: number;
  categories_count: number;
  models_count: number;
  visible_brands_truncated: boolean;
  categories_truncated: boolean;
  models_truncated: boolean;
  visible_brands: Array<{
    id: number | string;
    title: string;
  }>;
  categories: Array<{
    id: string;
    title: string;
    quantity: string;
  }>;
  models: Array<{
    name: string;
  }>;
  visible_brands_preview: Array<{
    id: number | string;
    title: string;
  }>;
  categories_preview: Array<{
    id: number | string;
    title: string;
  }>;
  models_preview: Array<{
    name: string;
  }>;
  price_columns: string[];
  warehouse_columns: string[];
  last_error_message: string;
};

export type BackofficeUtrBrandImportSummary = {
  total_received: number;
  processed: number;
  created: number;
  updated: number;
  skipped: number;
  duplicate_in_payload: number;
  errors: number;
};
