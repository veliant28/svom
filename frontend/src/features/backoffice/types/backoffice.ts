export type BackofficeUser = {
  id: string;
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  preferred_language: "uk" | "ru" | "en";
  is_staff: boolean;
  is_superuser: boolean;
};

export type BackofficeImportSource = {
  id: string;
  code: string;
  name: string;
  supplier_code: string;
  supplier_name: string;
  parser_type: string;
  input_path: string;
  file_patterns: string[];
  default_currency: string;
  auto_reprice: boolean;
  auto_reindex: boolean;
  is_auto_import_enabled: boolean;
  schedule_cron: string;
  schedule_timezone: string;
  auto_reprice_after_import: boolean;
  auto_reindex_after_import: boolean;
  last_started_at: string | null;
  last_finished_at: string | null;
  last_success_at: string | null;
  last_failed_at: string | null;
  is_active: boolean;
  last_run: {
    id: string;
    status: string;
    processed_rows: number;
    errors_count: number;
    offers_created: number;
    offers_updated: number;
    finished_at: string | null;
    created_at: string;
  } | null;
  next_run: string | null;
  created_at: string;
  updated_at: string;
};

export type BackofficeCatalogBrand = {
  id: string;
  name: string;
  slug: string;
  country: string;
  description: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type BackofficeCatalogCategory = {
  id: string;
  name: string;
  name_uk: string;
  name_ru: string;
  name_en: string;
  slug: string;
  parent: string | null;
  parent_name: string;
  description: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type BackofficeCatalogProduct = {
  id: string;
  sku: string;
  article: string;
  name: string;
  slug: string;
  brand: string;
  brand_name: string;
  category: string;
  category_name: string;
  final_price: string | null;
  currency: string | null;
  price_updated_at: string | null;
  supplier_price: string | null;
  supplier_currency: string | null;
  applied_markup_percent: string | null;
  applied_markup_policy_name: string;
  applied_markup_policy_scope: string;
  warehouse_segments: Array<{
    key: string;
    value: string;
    source_code: string;
  }>;
  supplier_sku: string;
  short_description: string;
  description: string;
  is_active: boolean;
  is_featured: boolean;
  is_new: boolean;
  is_bestseller: boolean;
  created_at: string;
  updated_at: string;
};

export type BackofficeVehicleMake = {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type BackofficeVehicleModel = {
  id: string;
  make: string;
  make_name: string;
  name: string;
  slug: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type BackofficeVehicleGeneration = {
  id: string;
  model: string;
  model_name: string;
  make_name: string;
  name: string;
  year_start: number | null;
  year_end: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type BackofficeVehicleEngine = {
  id: string;
  generation: string;
  generation_name: string;
  model_name: string;
  make_name: string;
  name: string;
  code: string;
  fuel_type: string;
  displacement_cc: number | null;
  power_hp: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type BackofficeVehicleModification = {
  id: string;
  engine: string;
  engine_name: string;
  generation_name: string;
  model_name: string;
  make_name: string;
  name: string;
  body_type: string;
  transmission: string;
  drivetrain: string;
  year_start: number | null;
  year_end: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type BackofficeProductFitment = {
  id: string;
  product: string;
  product_name: string;
  product_sku: string;
  modification: string;
  modification_name: string;
  engine_name: string;
  generation_name: string;
  model_name: string;
  make_name: string;
  note: string;
  is_exact: boolean;
  created_at: string;
  updated_at: string;
};

export type BackofficeAutocatalogCar = {
  year: number | null;
  make: string;
  model: string;
  modification: string;
  capacity: string;
  engine: string;
  hp: number | null;
  kw: number | null;
};

export type BackofficeAutocatalogFilterOptions = {
  years: number[];
  makes: string[];
  models: string[];
  modifications: string[];
  capacities: string[];
  engines: string[];
};

export type BackofficeSupplierBrandAlias = {
  id: string;
  source: string | null;
  source_code: string;
  supplier: string | null;
  supplier_code: string;
  supplier_name: string;
  canonical_brand: string | null;
  canonical_brand_name: string;
  canonical_brand_label: string;
  supplier_brand_alias: string;
  normalized_alias: string;
  is_active: boolean;
  priority: number;
  notes: string;
  created_at: string;
  updated_at: string;
};

export type BackofficeArticleRule = {
  id: string;
  source: string | null;
  source_code: string;
  name: string;
  rule_type: "remove_separators" | "strip_prefix" | "strip_suffix" | "regex_replace" | "force_uppercase";
  pattern: string;
  replacement: string;
  is_active: boolean;
  priority: number;
  notes: string;
  created_at: string;
  updated_at: string;
};

export type BackofficeImportQuality = {
  id: string;
  run_id: string;
  source: string;
  source_code: string;
  source_name: string;
  previous_run_id: string;
  status: string;
  total_rows: number;
  matched_rows: number;
  auto_matched_rows: number;
  manual_matched_rows: number;
  ignored_rows: number;
  unmatched_rows: number;
  conflict_rows: number;
  error_rows: number;
  match_rate: number;
  error_rate: number;
  match_rate_delta: number;
  error_rate_delta: number;
  flags: Array<Record<string, unknown>>;
  requires_operator_attention: boolean;
  summary: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type BackofficeImportQualitySummary = {
  generated_at: string;
  totals: {
    total_quality_runs: number;
    attention_runs: number;
    failed_runs: number;
    partial_runs: number;
    avg_match_rate: number;
    avg_error_rate: number;
    attention_runs_24h: number;
  };
  latest_by_supplier: Array<{
    source_code: string;
    source_name: string;
    match_rate: number;
    error_rate: number;
    status: string;
    requires_operator_attention: boolean;
  }>;
  attention_runs: Array<{
    run_id: string;
    source_code: string;
    status: string;
    match_rate: number;
    error_rate: number;
    flags: Array<Record<string, unknown>>;
    created_at: string;
  }>;
};

export type BackofficeImportQualityComparison = {
  run_id: string;
  source_code: string;
  current: Record<string, unknown> | null;
  previous: Record<string, unknown> | null;
  delta: {
    match_rate: number;
    error_rate: number;
  };
  flags: Array<Record<string, unknown>>;
  requires_operator_attention: boolean;
};

export type BackofficeImportArtifact = {
  id: string;
  file_name: string;
  file_format: string;
  file_size: number;
  status: string;
  parsed_rows: number;
  errors_count: number;
  created_at: string;
  updated_at: string;
};

export type BackofficeImportRun = {
  id: string;
  source: string;
  source_code: string;
  source_name: string;
  status: string;
  trigger: string;
  dry_run: boolean;
  started_at: string | null;
  finished_at: string | null;
  processed_rows: number;
  parsed_rows: number;
  offers_created: number;
  offers_updated: number;
  offers_skipped: number;
  errors_count: number;
  repriced_products: number;
  reindexed_products: number;
  summary: Record<string, unknown>;
  note: string;
  artifacts: BackofficeImportArtifact[];
  created_at: string;
  updated_at: string;
};

export type BackofficeImportError = {
  id: string;
  run: string;
  artifact: string | null;
  source: string;
  source_code: string;
  source_name: string;
  row_number: number | null;
  external_sku: string;
  error_code: string;
  message: string;
  raw_payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type BackofficeRawOffer = {
  id: string;
  run: string;
  source: string;
  source_code: string;
  supplier: string;
  supplier_code: string;
  supplier_name: string;
  artifact: string | null;
  row_number: number | null;
  external_sku: string;
  article: string;
  normalized_article: string;
  brand_name: string;
  normalized_brand: string;
  product_name: string;
  currency: string;
  price: string | null;
  stock_qty: number;
  lead_time_days: number;
  matched_product: string | null;
  product_id: string | null;
  matched_product_name?: string;
  matched_product_sku?: string;
  matched_product_article?: string;
  match_status: "unmatched" | "auto_matched" | "manual_match_required" | "manually_matched" | "ignored";
  match_reason: "" | "brand_conflict" | "article_conflict" | "ambiguous_match" | "missing_brand" | "missing_article";
  match_candidate_product_ids: string[];
  matching_attempts: number;
  last_matched_at: string | null;
  matched_manually_by: string | null;
  matched_manually_at: string | null;
  ignored_at: string | null;
  mapped_category: string | null;
  mapped_category_name: string;
  mapped_category_path: string;
  category_mapping_status: "unmapped" | "auto_mapped" | "manual_mapped" | "needs_review";
  category_mapping_reason: string;
  category_mapping_confidence: string | null;
  category_mapped_at: string | null;
  category_mapped_by: string | null;
  is_valid: boolean;
  skip_reason: string;
  raw_payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type BackofficeCategoryMappingCategoryOption = {
  id: string;
  name: string;
  breadcrumb: string;
  is_leaf: boolean;
};

export type BackofficeRawOfferCategoryMappingDetail = {
  id: string;
  supplier_code: string;
  supplier_name: string;
  external_sku: string;
  article: string;
  brand_name: string;
  product_name: string;
  match_status: BackofficeRawOffer["match_status"];
  matched_product_id: string | null;
  matched_product_name: string;
  matched_product_category: BackofficeCategoryMappingCategoryOption | null;
  mapped_category: BackofficeCategoryMappingCategoryOption | null;
  category_mapping_status: BackofficeRawOffer["category_mapping_status"];
  category_mapping_reason: string;
  category_mapping_confidence: string | null;
  category_mapped_at: string | null;
  category_mapped_by: string | null;
  updated_at: string;
};

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

export type BackofficeProductPrice = {
  id: string;
  product_id: string;
  product_name: string;
  product_sku: string;
  product_article: string;
  brand_name: string;
  category_name: string;
  currency: string;
  purchase_price: string;
  logistics_cost: string;
  extra_cost: string;
  landed_cost: string;
  raw_sale_price: string;
  final_price: string;
  policy: string | null;
  policy_name: string;
  auto_calculation_locked: boolean;
  recalculated_at: string | null;
  updated_at: string;
};

export type BackofficePricingControlPanel = {
  summary: {
    products_total: number;
    priced_total: number;
    featured_total: number;
    non_featured_total: number;
    category_policies_total: number;
  };
  global_policy: {
    id: string;
    name: string;
    percent_markup: string;
    is_active: boolean;
    updated_at: string;
  } | null;
  top_segment: {
    supported: boolean;
    reason: string;
  };
  chart: {
    markup_buckets: Array<{
      key: string;
      label: string;
      count: number;
    }>;
    policy_distribution: Array<{
      label: string;
      count: number;
    }>;
  };
};

export type BackofficePricingCategoryImpact = {
  category_id: string;
  include_children: boolean;
  target_category_ids: string[];
  target_categories: Array<{
    id: string;
    name: string;
  }>;
  affected_products: number;
  current_percent_markup: string | null;
};

export type BackofficeSummary = {
  generated_at: string;
  totals: {
    sources: number;
    import_runs: number;
    errors_total: number;
    errors_24h: number;
    raw_offers: number;
    raw_offers_invalid: number;
    unmatched_offers: number;
    conflict_offers: number;
    auto_matched_offers: number;
    manually_resolved_offers: number;
    supplier_offers: number;
    product_prices: number;
    repriced_products_total: number;
  };
  status_buckets: Array<{ status: string; total: number }>;
  latest_runs: Array<{
    id: string;
    source_code: string;
    source_name: string;
    status: string;
    dry_run: boolean;
    processed_rows: number;
    errors_count: number;
    offers_created: number;
    offers_updated: number;
    repriced_products: number;
    finished_at: string | null;
    created_at: string;
  }>;
  quality_summary?: {
    run_id: string;
    source_code: string;
    processed_rows: number;
    errors_count: number;
    error_rate: number;
    offers_created: number;
    offers_updated: number;
    offers_skipped: number;
  };
  quality_trend?: Array<{
    run_id: string;
    source_code: string;
    match_rate: number;
    error_rate: number;
    requires_operator_attention: boolean;
    status: string;
    created_at: string;
  }>;
  match_rate_by_supplier?: Array<{
    source_code: string;
    source_name: string;
    match_rate: number;
    error_rate: number;
    status: string;
    requires_operator_attention: boolean;
  }>;
  recent_failed_partial?: Array<{
    id: string;
    source_code: string;
    status: string;
    errors_count: number;
    processed_rows: number;
    created_at: string;
  }>;
  recent_degraded_imports?: Array<{
    run_id: string;
    source_code: string;
    status: string;
    match_rate: number;
    error_rate: number;
    flags: Array<Record<string, unknown>>;
    created_at: string;
  }>;
  requires_operator_attention?: Array<{
    run_id: string;
    source_code: string;
    status: string;
    flags: Array<Record<string, unknown>>;
    match_rate: number;
    error_rate: number;
    created_at: string;
  }>;
};

export type BackofficeMatchingSummary = {
  unmatched: number;
  conflicts: number;
  auto_matched: number;
  manually_matched: number;
  ignored: number;
};

export type BackofficeMatchingCandidateProduct = {
  id: string;
  name: string;
  sku: string;
  article: string;
  brand_name: string;
  category_name: string;
};

export type BackofficeActionResponse = {
  mode: "sync" | "async";
  task_id?: string;
  run_id?: string;
  status?: string;
  result?: Record<string, unknown>;
  results?: Array<Record<string, unknown>>;
  sources?: number;
  stats?: Record<string, unknown>;
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

export type BackofficeOrderOperationalItem = {
  id: string;
  product_id: string;
  product_name: string;
  product_sku: string;
  quantity: number;
  unit_price: string;
  line_total: string;
  procurement_status: string;
  recommended_supplier_offer_id: string | null;
  recommended_supplier_name: string;
  selected_supplier_offer_id: string | null;
  selected_supplier_name: string;
  shortage_reason_code: string;
  shortage_reason_note: string;
  operator_note: string;
  snapshot_availability_status: string;
  snapshot_availability_label: string;
  snapshot_estimated_delivery_days: number | null;
  snapshot_procurement_source: string;
  snapshot_currency: string;
  snapshot_sell_price: string;
};

export type BackofficeOrderOperational = {
  id: string;
  order_number: string;
  status: string;
  user_id: string;
  user_email: string;
  contact_full_name: string;
  contact_phone: string;
  contact_email: string;
  delivery_method: string;
  payment_method: string;
  subtotal: string;
  delivery_fee: string;
  total: string;
  currency: string;
  items_count: number;
  issues_count: number;
  placed_at: string;
  customer_comment?: string;
  internal_notes?: string;
  operator_notes?: string;
  cancellation_reason_code?: string;
  cancellation_reason_note?: string;
  items?: BackofficeOrderOperationalItem[];
};

export type BackofficeProcurementOffer = {
  offer_id: string | null;
  supplier_id: string | null;
  supplier_code: string;
  supplier_name: string;
  supplier_sku: string;
  purchase_price: string | null;
  currency: string;
  stock_qty: number;
  lead_time_days: number | null;
  is_available: boolean;
};

export type BackofficeProcurementRecommendation = {
  order_item_id: string;
  order_id: string;
  order_number?: string;
  product_id: string;
  product_name: string;
  product_sku: string;
  quantity: number;
  current_procurement_status: string;
  recommended_offer: BackofficeProcurementOffer;
  selected_offer_id: string | null;
  can_fulfill: boolean;
  partially_available: boolean;
  fallback_used: boolean;
  availability_status: string;
  availability_label: string;
  eta_days: number | null;
  issues: string[];
};

export type BackofficeProcurementSupplierGroup = {
  supplier_id: string | null;
  supplier_code: string;
  supplier_name: string;
  items: BackofficeProcurementRecommendation[];
  items_count: number;
  total_quantity: number;
};

export type BackofficeProcurementSuggestions = {
  groups: BackofficeProcurementSupplierGroup[];
  groups_count: number;
  items_count: number;
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
