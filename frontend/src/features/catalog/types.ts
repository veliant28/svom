export type BrandSummary = {
  id: string;
  name: string;
  slug: string;
};

export type CategorySummary = {
  id: string;
  name: string;
  slug: string;
  sort_order?: number;
  is_assignable?: boolean;
  parent?: {
    id: string;
    name: string;
    slug: string;
    sort_order?: number;
  } | null;
};

export type CatalogProduct = {
  id: string;
  sku: string;
  article: string;
  manufacturer_article?: string;
  name: string;
  slug: string;
  short_description: string;
  brand: BrandSummary;
  category: CategorySummary;
  primary_image: string;
  final_price: string;
  currency: string;
  availability_status: string;
  availability_label: string;
  estimated_delivery_days: number | null;
  procurement_source_summary: string;
  is_sellable: boolean;
  total_stock_qty: number;
  is_featured: boolean;
  is_new: boolean;
  is_bestseller: boolean;
  has_fitment_data: boolean;
  fits_selected_vehicle: boolean | null;
  fitment_count?: number;
  is_autodb_compatible_data_available?: boolean;
  link_quality_status?: string;
  vehicle_filter_policy?: "strict_fitment" | "show_all_with_badges";
  selected_vehicle_compatibility?: {
    vehicle_id: number;
    is_compatible: boolean;
  } | null;
};

export type CatalogFilters = {
  q?: string;
  brand?: string;
  category?: string;
  category_id?: string;
  min_price?: string;
  max_price?: string;
  is_featured?: boolean;
  is_new?: boolean;
  is_bestseller?: boolean;
  modification?: string;
  vehicle_id?: string;
  passanger_car_id?: string;
  garage_vehicle?: string;
  fitment?: "all" | "only" | "unknown" | "with_data";
};

export type ProductImage = {
  id: string;
  image_url: string;
  alt_text: string;
  is_primary: boolean;
  sort_order: number;
};

export type ProductAttribute = {
  id: string;
  attribute_name: string;
  value: string;
};

export type ProductFitment = {
  id: string;
  vehicle_id?: number;
  make: string;
  model: string;
  generation: string;
  engine: string;
  modification: string;
  body?: string;
  label?: string;
  subtitle?: string;
  note: string;
  is_exact: boolean;
};

export type ProductFitmentOption = {
  value: string;
  label: string;
};

export type ProductFitmentOptions = {
  makes: ProductFitmentOption[];
  models: ProductFitmentOption[];
  modifications?: ProductFitmentOption[];
  selected_make: string;
  selected_model: string;
  selected_modification?: string;
  total_fitments: number;
};

export type ProductCompatibilitySummaryVehicle = {
  vehicle_id: number;
  is_compatible?: boolean;
  make: string;
  model: string;
  modification: string;
  years: string;
  engine: string;
  body?: string;
  label: string;
  subtitle: string;
};

export type ProductCompatibilitySummary = {
  available: boolean;
  fitment_count: number;
  selected_vehicle: ProductCompatibilitySummaryVehicle | null;
  sample_vehicles: ProductCompatibilitySummaryVehicle[];
};

export type ProductFitmentRowsResponse = {
  count: number;
  next_offset: number | null;
  results: ProductFitment[];
};

export type ProductDetail = {
  id: string;
  sku: string;
  article: string;
  manufacturer_article?: string;
  name: string;
  slug: string;
  short_description: string;
  description: string;
  brand: BrandSummary;
  category: CategorySummary;
  images: ProductImage[];
  attributes: ProductAttribute[];
  fitments: ProductFitment[];
  final_price: string;
  currency: string;
  availability_status: string;
  availability_label: string;
  estimated_delivery_days: number | null;
  procurement_source_summary: string;
  is_sellable: boolean;
  total_stock_qty: number;
  is_featured: boolean;
  is_new: boolean;
  is_bestseller: boolean;
  has_fitment_data: boolean;
  fits_selected_vehicle: boolean | null;
  fitment_badge_hidden?: boolean;
  fitment_count?: number;
  is_autodb_compatible_data_available?: boolean;
  link_quality_status?: string;
  vehicle_filter_policy?: "strict_fitment" | "show_all_with_badges";
  compatibility_summary?: ProductCompatibilitySummary;
};

export type PaginatedResponse<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};
