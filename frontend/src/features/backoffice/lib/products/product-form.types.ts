export type ProductModalMode = "create" | "edit";

export type CategoryOption = {
  id: string;
  label: string;
};

export type ProductFormState = {
  sku: string;
  article: string;
  name: string;
  brand: string;
  category: string;
  is_active: boolean;
  is_featured: boolean;
  is_new: boolean;
  is_bestseller: boolean;
};

export const DEFAULT_PRODUCT_FORM_STATE: ProductFormState = {
  sku: "",
  article: "",
  name: "",
  brand: "",
  category: "",
  is_active: true,
  is_featured: false,
  is_new: false,
  is_bestseller: false,
};
