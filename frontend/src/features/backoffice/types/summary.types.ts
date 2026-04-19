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
