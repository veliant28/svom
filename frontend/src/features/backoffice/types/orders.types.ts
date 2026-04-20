export type BackofficeOrderOperationalItem = {
  id: string;
  product_id: string;
  product_name: string;
  product_sku: string;
  quantity: number;
  unit_price: string;
  line_total: string;
  procurement_status: string;
  recommended_supplier_offer_id: string | null;
  recommended_supplier_name: string;
  selected_supplier_offer_id: string | null;
  selected_supplier_name: string;
  shortage_reason_code: string;
  shortage_reason_note: string;
  operator_note: string;
  snapshot_availability_status: string;
  snapshot_availability_label: string;
  snapshot_estimated_delivery_days: number | null;
  snapshot_procurement_source: string;
  snapshot_currency: string;
  snapshot_sell_price: string;
};

export type BackofficeOrderPayment = {
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

export type BackofficeMonobankPaymentAction = "refresh" | "cancel" | "remove" | "finalize" | "fiscal_checks";

export type BackofficeMonobankFiscalCheck = {
  id: string;
  status: string;
  type: string;
  statusDescription: string;
  taxUrl: string;
  file: string;
  fiscalizationSource: string;
};

export type BackofficeMonobankPaymentActionResult = {
  action: BackofficeMonobankPaymentAction;
  payment: BackofficeOrderPayment;
  provider_result: Record<string, unknown>;
  fiscal_checks: BackofficeMonobankFiscalCheck[];
};

export type BackofficeOrderDeliveryWaybillSeed = {
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

export type BackofficeOrderOperational = {
  id: string;
  order_number: string;
  status: string;
  user_id: string;
  user_email: string;
  contact_full_name: string;
  contact_phone: string;
  contact_email: string;
  delivery_method: string;
  delivery_address: string;
  delivery_snapshot: Record<string, unknown>;
  delivery_city_label: string;
  delivery_destination_label: string;
  delivery_waybill_seed: BackofficeOrderDeliveryWaybillSeed;
  payment_method: string;
  payment: BackofficeOrderPayment;
  subtotal: string;
  delivery_fee: string;
  total: string;
  currency: string;
  items_count: number;
  issues_count: number;
  nova_poshta_waybill_exists: boolean;
  nova_poshta_waybill_number: string;
  nova_poshta_waybill_status_code: string;
  nova_poshta_waybill_status_text: string;
  nova_poshta_waybill_has_error: boolean;
  placed_at: string;
  customer_comment?: string;
  internal_notes?: string;
  operator_notes?: string;
  cancellation_reason_code?: string;
  cancellation_reason_note?: string;
  items?: BackofficeOrderOperationalItem[];
};

export type BackofficeProcurementOffer = {
  offer_id: string | null;
  supplier_id: string | null;
  supplier_code: string;
  supplier_name: string;
  supplier_sku: string;
  purchase_price: string | null;
  currency: string;
  stock_qty: number;
  lead_time_days: number | null;
  is_available: boolean;
};

export type BackofficeProcurementRecommendation = {
  order_item_id: string;
  order_id: string;
  order_number?: string;
  product_id: string;
  product_name: string;
  product_sku: string;
  quantity: number;
  current_procurement_status: string;
  recommended_offer: BackofficeProcurementOffer;
  selected_offer_id: string | null;
  can_fulfill: boolean;
  partially_available: boolean;
  fallback_used: boolean;
  availability_status: string;
  availability_label: string;
  eta_days: number | null;
  issues: string[];
};

export type BackofficeProcurementSupplierGroup = {
  supplier_id: string | null;
  supplier_code: string;
  supplier_name: string;
  items: BackofficeProcurementRecommendation[];
  items_count: number;
  total_quantity: number;
};

export type BackofficeProcurementSuggestions = {
  groups: BackofficeProcurementSupplierGroup[];
  groups_count: number;
  items_count: number;
};

export type BackofficeOrderDeleteResult = {
  order_id: string;
  order_number: string;
};

export type BackofficeOrderBulkDeleteResult = {
  deleted: number;
  skipped: Array<{ order_id: string; reason: string }>;
};

export type BackofficeGplOrderStatus = {
  id: number;
  slug: string;
  name: string;
};

export type BackofficeGplOrderCurrency = {
  id: number;
  currency: string;
  symbol: string;
};

export type BackofficeGplOrderProduct = {
  id: number;
  article: string;
  name: string;
  weight: string;
  unit: string;
  count: number;
  price: string;
};

export type BackofficeGplOrder = {
  id: number;
  weight: string | number;
  price: string | number;
  created_at: string;
  products: BackofficeGplOrderProduct[];
  status: BackofficeGplOrderStatus;
  currency: BackofficeGplOrderCurrency;
};

export type BackofficeGplOrdersResponse = {
  data: BackofficeGplOrder[];
  code?: number;
  status?: string;
  message?: string;
};

export type BackofficeGplOrderResponse = {
  data: BackofficeGplOrder;
  code?: number;
  status?: string;
  message?: string;
};

export type BackofficeOrderSupplierPayloadItem = {
  item_id: string;
  product_name: string;
  product_sku: string;
  quantity: number;
  unit_price: string;
  line_total: string;
  gpl_product_id: number | null;
  is_sendable: boolean;
};

export type BackofficeOrderSupplierPayloadPreview = {
  order_id: string;
  order_number: string;
  products: Array<{ id: number; count: number }>;
  items: BackofficeOrderSupplierPayloadItem[];
  can_submit: boolean;
  missing_count: number;
  last_supplier_order_id: number | null;
};

export type BackofficeOrderSupplierCreateResult = {
  order_id: string;
  order_number: string;
  supplier_order_id: number | null;
  products: Array<{ id: number; count: number }>;
  response: BackofficeGplOrderResponse;
};

export type BackofficeOrderSupplierCancelResult = {
  order_id: string;
  order_number: string;
  supplier_order_id: number;
  response: BackofficeGplOrderResponse;
};
