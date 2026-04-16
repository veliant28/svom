export type CommerceProductSummary = {
  id: string;
  sku: string;
  name: string;
  slug: string;
  brand_name: string;
  primary_image: string;
  final_price: string;
  currency: string;
};

export type WishlistItem = {
  id: string;
  product: CommerceProductSummary;
  created_at: string;
};

export type CartItem = {
  id: string;
  product: CommerceProductSummary;
  quantity: number;
  unit_price: string;
  line_total: string;
  availability_status: string;
  availability_label: string;
  estimated_delivery_days: number | null;
  procurement_source_summary: string;
  is_sellable: boolean;
  warning: string;
};

export type CartSummary = {
  items_count: number;
  subtotal: string;
  warnings_count: number;
};

export type Cart = {
  id: string;
  currency: string;
  items: CartItem[];
  summary: CartSummary;
  updated_at: string;
};

export type CheckoutPreview = {
  items_count: number;
  subtotal: string;
  delivery_fee: string;
  total: string;
  warnings: Array<{
    product_id: string;
    product_name: string;
    product_sku: string;
    warning: string;
  }>;
};

export type CheckoutPreviewResponse = {
  cart: Cart;
  checkout_preview: CheckoutPreview;
};

export type OrderItem = {
  id: string;
  product: CommerceProductSummary;
  product_name: string;
  product_sku: string;
  quantity: number;
  unit_price: string;
  line_total: string;
  procurement_status: string;
  recommended_supplier_offer_id: string | null;
  selected_supplier_offer_id: string | null;
  shortage_reason_code: string;
  shortage_reason_note: string;
  operator_note: string;
  snapshot_currency: string;
  snapshot_sell_price: string;
  snapshot_availability_status: string;
  snapshot_availability_label: string;
  snapshot_estimated_delivery_days: number | null;
  snapshot_procurement_source: string;
  snapshot_selected_offer: string | null;
  snapshot_offer_explainability: Record<string, unknown>;
};

export type Order = {
  id: string;
  order_number: string;
  status:
    | "new"
    | "confirmed"
    | "awaiting_procurement"
    | "reserved"
    | "partially_reserved"
    | "ready_to_ship"
    | "shipped"
    | "completed"
    | "cancelled"
    | "draft"
    | "placed";
  contact_full_name: string;
  contact_phone: string;
  contact_email: string;
  delivery_method: "pickup" | "courier" | "nova_poshta";
  delivery_address: string;
  payment_method: "cash_on_delivery" | "card_placeholder";
  subtotal: string;
  delivery_fee: string;
  total: string;
  currency: string;
  customer_comment: string;
  internal_notes?: string;
  operator_notes?: string;
  cancellation_reason_code?: string;
  cancellation_reason_note?: string;
  placed_at: string;
  items: OrderItem[];
};
