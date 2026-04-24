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
  schedule_start_date: string | null;
  schedule_run_time: string;
  schedule_every_day: boolean;
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
    offers_skipped: number;
    offers_created: number;
    offers_updated: number;
    finished_at: string | null;
    created_at: string;
  } | null;
  next_run: string | null;
  created_at: string;
  updated_at: string;
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
