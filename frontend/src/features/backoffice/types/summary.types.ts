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
    published_products: number;
    product_prices: number;
    repriced_products_total: number;
    repriced_products_24h: number;
  };
  orders_unprocessed?: {
    count: number;
    oldest_created_at: string | null;
    oldest_order_number: string;
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

export type BackofficeStaffActivityRole = "manager" | "operator";

export type BackofficeStaffActivityPayload = {
  generated_at: string;
  role: BackofficeStaffActivityRole;
  days: number;
  kpis: {
    staff_total: number;
    with_activity_total: number;
    actions_total: number;
    ttn_actions_total: number;
    loyalty_issued_total: number;
    price_changes_total: number;
  };
  chart_by_day: Array<{
    date: string;
    ttn_actions: number;
    loyalty_issued: number;
    price_changes: number;
    total: number;
  }>;
  staff: Array<{
    staff_id: string;
    staff_email: string;
    staff_name: string;
    actions_total: number;
    ttn_actions: number;
    ttn_orders: number;
    loyalty_issued: number;
    loyalty_used: number;
    loyalty_discount_sum: string;
    price_changes: number;
    price_manual: number;
    price_import: number;
    price_auto: number;
    last_activity_at: string | null;
  }>;
};
