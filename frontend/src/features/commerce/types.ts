import type { CatalogProduct } from "@/features/catalog/types";

export type CommerceProductSummary = {
  id: string;
  sku: string;
  article?: string;
  manufacturer_article?: string;
  name: string;
  slug: string;
  brand_name: string;
  primary_image: string;
  final_price: string;
  currency: string;
};

export type WishlistItem = {
  id: string;
  product: CatalogProduct | null;
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

export type OrderReceipt = {
  provider: string;
  available: boolean;
  status_code: number | null;
  status_key: string;
  status_label: string;
  check_fn: string;
  can_open: boolean;
  error_message: string;
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
  payment_method: "cash_on_delivery" | "monobank" | "novapay" | "liqpay" | "card_placeholder";
  payment?: OrderPayment | null;
  receipt: OrderReceipt;
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

export type ReturnStatus =
  | "new"
  | "approved"
  | "rejected"
  | "awaiting_ttn"
  | "in_transit"
  | "received"
  | "accepted"
  | "refunded"
  | "cancelled";

export type ReturnRequestListItem = {
  id: string;
  return_number: string;
  order_number: string;
  created_at: string;
  return_day_label: string;
  status: ReturnStatus;
  refund_amount: string;
  tracking_number: string;
};

export type ReturnRequestItem = {
  id: string;
  order_item: string;
  product: string;
  product_name_snapshot: string;
  product_sku_snapshot: string;
  quantity_ordered: number;
  quantity_requested: number;
  quantity_approved: number;
  original_unit_price: string;
  original_line_total: string;
  refund_amount: string;
  is_returnable_snapshot: boolean;
  non_returnable_reason_snapshot: string;
  display_sku: string;
  display_brand: string;
  display_article: string;
  display_name: string;
};

export type ReturnShippingAddress = {
  recipient_full_name: string;
  recipient_phone: string;
  region_ref: string;
  region_label: string;
  city_ref: string;
  city_label: string;
  np_warehouse_text: string;
};

export type ReturnRequestDetail = {
  id: string;
  return_number: string;
  order: string;
  order_number: string;
  status: ReturnStatus;
  reason_comment: string;
  admin_comment: string;
  rejection_reason: string;
  refund_amount: string;
  refund_status: string;
  refund_method: string;
  tracking_number: string;
  customer_return_tracking_submitted_at: string | null;
  can_edit_tracking_number: boolean;
  nova_poshta_return_status_code: string;
  nova_poshta_return_status_text: string;
  nova_poshta_return_status_synced_at: string | null;
  shipping_address: ReturnShippingAddress;
  received_at: string | null;
  approved_at: string | null;
  rejected_at: string | null;
  accepted_at: string | null;
  refund_processing_at: string | null;
  refunded_at: string | null;
  created_at: string;
  updated_at: string;
  return_day_label: string;
  items: ReturnRequestItem[];
};

export type EligibleReturnOrder = {
  id: string;
  order_number: string;
  total: string;
  currency: string;
  status: string;
  placed_at: string;
  return_day_label: string;
  items_count: number;
};

export type EligibleReturnOrderItem = {
  order_item_id: string;
  product_id: string;
  product: CommerceProductSummary;
  product_name: string;
  product_sku: string;
  quantity_ordered: number;
  max_return_quantity: number;
  unit_price: string;
  line_total: string;
  is_returnable: boolean;
  non_returnable_reason: string;
};

export type EligibleReturnOrderDetail = {
  order: EligibleReturnOrder;
  items: EligibleReturnOrderItem[];
};

export type CommerceOrderUpdatedEvent = {
  type: "commerce.order.updated";
  payload: {
    order_id: string;
    order_number: string;
    status: Order["status"];
  };
};

export type CommerceReturnUpdatedEvent = {
  type: "commerce.return.updated";
  payload: {
    return_id: string;
    return_number: string;
    order_number: string;
    status: ReturnStatus;
    tracking_number: string;
    admin_comment: string;
  };
};

export type CommerceRealtimeEvent =
  | { type: "commerce.connection.ready"; payload: { user_id: string } }
  | CommerceOrderUpdatedEvent
  | CommerceReturnUpdatedEvent;
