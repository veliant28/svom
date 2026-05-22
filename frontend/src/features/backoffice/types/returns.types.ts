import type { ReturnStatus } from "@/features/commerce/types";
import type { BackofficeStaffActor } from "@/features/backoffice/types/orders.types";

export type BackofficeReturnItem = {
  id: string;
  order_item: string;
  product: string;
  product_display_name?: string;
  product_svom_sku?: string;
  product_name_snapshot: string;
  product_sku_snapshot: string;
  supplier_name?: string;
  supplier_code?: string;
  quantity_ordered: number;
  quantity_requested: number;
  quantity_approved: number;
  original_unit_price: string;
  original_line_total: string;
  refund_amount: string;
  is_returnable_snapshot: boolean;
  non_returnable_reason_snapshot: string;
};

export type BackofficeReturnEvent = {
  id: string;
  actor: string | null;
  actor_name: string;
  from_status: string;
  to_status: string;
  comment: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type BackofficeReturnOperational = {
  id: string;
  return_number: string;
  order: string;
  order_number: string;
  status: ReturnStatus;
  refund_amount: string;
  customer_name: string;
  customer_phone: string;
  customer_email: string;
  tracking_number: string;
  created_at: string;
  return_day_label: string;
  reason_comment?: string;
  admin_comment?: string;
  rejection_reason?: string;
  refund_status?: string;
  refund_method?: string;
  customer_return_tracking_submitted_at?: string | null;
  nova_poshta_return_status_code?: string;
  nova_poshta_return_status_text?: string;
  nova_poshta_return_status_synced_at?: string | null;
  return_address_snapshot?: Record<string, unknown>;
  received_at?: string | null;
  approved_at?: string | null;
  rejected_at?: string | null;
  accepted_at?: string | null;
  refund_processing_at?: string | null;
  refunded_at?: string | null;
  updated_at?: string;
  last_actor?: BackofficeStaffActor | null;
  items?: BackofficeReturnItem[];
  events?: BackofficeReturnEvent[];
};

export type BackofficeReturnStatusUpdatePayload = {
  status: ReturnStatus;
  admin_comment?: string;
  rejection_reason?: string;
  approved_items?: Array<{
    item_id: string;
    quantity_approved: number;
  }>;
};
