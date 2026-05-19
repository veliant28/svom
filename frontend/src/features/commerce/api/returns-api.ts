import { getJson, postJson } from "@/shared/api/http-client";

import type {
  EligibleReturnOrder,
  EligibleReturnOrderDetail,
  ReturnRequestDetail,
  ReturnRequestListItem,
} from "@/features/commerce/types";

export async function getReturnRequests(token: string): Promise<ReturnRequestListItem[]> {
  return getJson<ReturnRequestListItem[]>("/commerce/returns/", undefined, { token });
}

export async function getReturnRequestDetail(token: string, returnId: string): Promise<ReturnRequestDetail> {
  return getJson<ReturnRequestDetail>(`/commerce/returns/${returnId}/`, undefined, { token });
}

export async function getEligibleReturnOrders(token: string): Promise<EligibleReturnOrder[]> {
  return getJson<EligibleReturnOrder[]>("/commerce/returns/eligible-orders/", undefined, { token });
}

export async function getEligibleReturnOrderDetail(token: string, orderId: string): Promise<EligibleReturnOrderDetail> {
  return getJson<EligibleReturnOrderDetail>(`/commerce/returns/eligible-orders/${orderId}/`, undefined, { token });
}

export async function createReturnRequest(
  token: string,
  payload: {
    order_id: string;
    items: Array<{ order_item_id: string; quantity: number }>;
    reason_comment: string;
  },
): Promise<ReturnRequestDetail> {
  return postJson<ReturnRequestDetail, typeof payload>("/commerce/returns/create/", payload, undefined, { token });
}

export async function submitReturnTrackingNumber(
  token: string,
  returnId: string,
  payload: { tracking_number: string },
): Promise<{ id: string; status: string; tracking_number: string; customer_return_tracking_submitted_at: string | null }> {
  return postJson<{ id: string; status: string; tracking_number: string; customer_return_tracking_submitted_at: string | null }, typeof payload>(
    `/commerce/returns/${returnId}/tracking/`,
    payload,
    undefined,
    { token },
  );
}
