export type AutoDbQuotaPoint = {
  timestamp: string;
  query_count: number;
  cumulative_used: number;
  run_id?: string;
  status?: string;
  error?: string;
};

export type AutoDbRemoteQuota = {
  status: "ok" | "warning" | "quota_paused" | string;
  estimated_limit_per_hour: number;
  estimated_queries_used: number;
  estimated_queries_remaining: number;
  usage_percent: number;
  window_started_at: string | null;
  expected_reset_at: string | null;
  seconds_until_reset: number;
  last_ok_at: string | null;
  last_query_at: string | null;
  last_quota_error_at: string | null;
  cooldown_until: string | null;
  recent_points: AutoDbQuotaPoint[];
};

export type AutoDbDashboard = {
  cards: Record<string, number | string>;
  jobs_by_status: Array<{ status: string; count: number }>;
  brand_coverage_distribution: Array<{ label: string; value: number }>;
  matching_funnel: Array<{ stage: string; count: number }>;
  source_breakdown: Array<{ source: string; count: number }>;
  remote_quota_usage: Array<{ label: string; used: number; paused: boolean }>;
  quota: {
    paused: boolean;
    estimated_queries_used: number;
    cooldown_until: string | null;
    last_error: string;
  };
  latest_run: {
    id: string;
    status: string;
    started_at: string | null;
    finished_at: string | null;
    checked: number;
    hits: number;
    safe_candidates: number;
    errors: number;
    quota_status: string;
    links_applied: number;
    enrichment_applied: number;
  };
  safety: Record<string, boolean>;
};

export type AutoDbProductJob = {
  id: string;
  product: {
    id: string;
    sku: string;
    svom_sku: string;
    name: string;
    brand: string;
    category: string;
    is_active: boolean;
    autodb_supplier_id: number | null;
    autodb_supplier_name: string;
    autodb_article_number: string;
    autodb_article_key: string;
    supplier_codes: string[];
  };
  supplier_code: string;
  raw_brand: string;
  normalized_brand: string;
  autodb_supplier_id: number | null;
  autodb_supplier_display: string;
  article_source: string;
  article_value: string;
  canonical_article: string;
  price: string;
  currency: string;
  stock_qty: number;
  has_product_price: boolean;
  tecdoc_status: "tecdoc" | "non_tecdoc" | "unknown" | string;
  matching_status: string;
  matching_status_view?: string;
  lookup_origin?: "local" | "remote" | string;
  lookup_method?: string;
  lookup_bucket?: "remote_brand_exact" | "remote_article_only" | "local_clone_hit" | "remote_other" | string;
  manual_remote_equivalent?: boolean;
  recommended_action: string;
  last_evidence: {
    stage: string;
    result: string;
    reason: string;
    created_at: string | null;
  };
  created_at: string | null;
  updated_at: string | null;
};

export type AutoDbJobsResponse = {
  count: number;
  results: AutoDbProductJob[];
};

export type AutoDbEvidence = {
  id?: string;
  stage?: string;
  source?: string;
  result?: string;
  supplier_id?: number | null;
  article_value?: string;
  canonical_article?: string;
  remote_stored_article?: string;
  article_prd_present?: boolean;
  prd_present?: boolean;
  reason?: string;
  payload?: Record<string, unknown>;
  created_at?: string | null;
};

export type AutoDbJobDetail = AutoDbProductJob & {
  drawer: {
    product_info: Record<string, unknown>;
    brand_resolution: Record<string, unknown>;
    article_source: Record<string, unknown>;
    local_lookup_evidence: AutoDbEvidence;
    remote_lookup_evidence: AutoDbEvidence;
    clone_sync_state: AutoDbEvidence;
    link_audit_result: AutoDbEvidence;
    enrichment_availability: {
      attributes_count: number;
      fitments_count: number;
      images_count_preview_only: number;
    };
    evidence: AutoDbEvidence[];
  };
};

export type AutoDbSearchResult = {
  source: "local" | "remote" | string;
  supplier_id: number | null;
  supplier_name: string;
  supplier_description?: string;
  supplier_matchcode?: string;
  article_input: string;
  variants: string[];
  searched_article: string;
  matched_stored_article: string;
  article_id: string;
  article_key: string;
  prd_linkage_present: boolean;
  prd_id: number | null;
  generic: string;
  category_metadata_present: boolean;
  attributes_available_count: number;
  fitments_available_count: number;
  images_available_count: number;
  image_thumbnails: string[];
  status: string;
  matched_table: string;
  source_path: string;
  confidence: string;
  reason: string;
  counts?: Record<string, number>;
  details?: Record<string, unknown>;
};

export type AutoDbSearchResponse = {
  dry_run: boolean;
  source: string;
  quota: AutoDbRemoteQuota;
  candidates?: Array<{
    supplier_id: number;
    supplier_name: string;
    matched_stored_article: string;
    hits: number;
    matched_table: string;
  }>;
  results: AutoDbSearchResult[];
};

export type AutoDbActionResponse = {
  dry_run: boolean;
  created?: boolean;
  status?: string;
  mode?: "async" | "sync" | string;
  task_id?: string;
  count?: number;
  message?: string;
  protected_fields?: Record<string, boolean>;
  results?: Array<Record<string, unknown>>;
  payload?: Record<string, unknown>;
  result?: Record<string, unknown>;
};

export type AutoDbSkuLookupRow = {
  id: string;
  sku: string;
  svom_sku: string;
  name: string;
  brand_name: string;
};

export type AutoDbSkuLookupResponse = {
  count: number;
  results: AutoDbSkuLookupRow[];
};
