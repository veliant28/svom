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
  supplier_price_levels: Array<{
    key: string;
    label: string;
    value: string;
    currency: string;
    is_primary: boolean;
    order: number;
  }>;
  applied_markup_percent: string | null;
  applied_markup_policy_name: string;
  applied_markup_policy_scope: string;
  warehouse_segments: Array<{
    key: string;
    value: string;
    source_code: string;
  }>;
  supplier_sku: string;
  supplier_offer_seen_at: string | null;
  short_description: string;
  description: string;
  is_active: boolean;
  is_featured: boolean;
  is_new: boolean;
  is_bestseller: boolean;
  created_at: string;
  updated_at: string;
};
