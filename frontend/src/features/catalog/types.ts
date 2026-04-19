export type BrandSummary = {
  id: string;
  name: string;
  slug: string;
};

export type CategorySummary = {
  id: string;
  name: string;
  slug: string;
  parent?: {
    id: string;
    name: string;
    slug: string;
  } | null;
};

export type CatalogProduct = {
  id: string;
  sku: string;
  article: string;
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
  car_modification?: string;
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
  make: string;
  model: string;
  generation: string;
  engine: string;
  modification: string;
  note: string;
  is_exact: boolean;
};

export type ProductDetail = {
  id: string;
  sku: string;
  article: string;
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
};

export type PaginatedResponse<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};
