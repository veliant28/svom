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
  max_order_quantity: number | null;
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
  discount_total: string;
  total: string;
  promo: {
    code: string;
    discount_type: "delivery_fee" | "product_markup";
    requested_percent: string;
    applied_percent: string;
    subtotal_before_discount: string;
    delivery_fee_before_discount: string;
    total_before_discount: string;
    product_markup_cap: {
      available_markup_total: string;
      requested_discount_amount: string;
      applied_discount_amount: string;
    };
    delivery_discount: string;
    product_discount: string;
    total_discount: string;
    total_after_discount: string;
    currency: string;
  } | null;
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

export type LoyaltyPromoCode = {
  id: string;
  code: string;
  discount_type: "delivery_fee" | "product_markup";
  discount_percent: string;
  reason: string;
  status: "active" | "disabled";
  state: "active" | "used" | "expired" | "disabled";
  is_active: boolean;
  is_used: boolean;
  is_expired: boolean;
  usage_limit: number;
  usage_count: number;
  expires_at: string | null;
  last_redeemed_at: string | null;
  created_at: string;
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

export type OrderPayment = {
  provider: string;
  method: string;
  status: string;
  amount: string;
  currency: string;
  invoice_id: string;
  reference: string;
  page_url: string;
  failure_reason: string;
  provider_created_at: string | null;
  provider_modified_at: string | null;
  last_webhook_received_at: string | null;
  last_sync_at: string | null;
};

export type OrderDeliveryWaybillSeed = {
  delivery_type: "warehouse" | "postomat" | "address";
  recipient_city_ref: string;
  recipient_city_label: string;
  recipient_address_ref: string;
  recipient_address_label: string;
  recipient_street_ref: string;
  recipient_street_label: string;
  recipient_house: string;
  recipient_apartment: string;
};

export type Order = {
  id: string;
  order_number: string;
  status:
    | "new"
    | "processing"
    | "ready_for_shipment"
    | "shipped"
    | "completed"
    | "cancelled";
  contact_full_name: string;
  contact_phone: string;
  contact_email: string;
  delivery_method: "pickup" | "courier" | "nova_poshta";
  delivery_address: string;
  delivery_snapshot: Record<string, unknown>;
  delivery_city_label: string;
  delivery_destination_label: string;
  delivery_waybill_seed: OrderDeliveryWaybillSeed;
  payment_method: "cash_on_delivery" | "monobank" | "liqpay" | "card_placeholder";
  payment?: OrderPayment | null;
  subtotal: string;
  delivery_fee: string;
  discount_total: string;
  applied_promo_code: string;
  discount_breakdown: Record<string, unknown>;
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
