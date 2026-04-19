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
