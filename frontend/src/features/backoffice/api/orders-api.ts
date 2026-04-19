import { deleteJson, getJson, patchJson, postJson } from "@/shared/api/http-client";
import { siteConfig } from "@/shared/config/site";
import { normalizePaginatedListResponse } from "@/shared/api/normalize-list-response";

import type {
  BackofficeGplOrderResponse,
  BackofficeGplOrdersResponse,
  BackofficeOrderBulkDeleteResult,
  BackofficeOrderDeleteResult,
  BackofficeOrderOperational,
  BackofficeOrderSupplierCancelResult,
  BackofficeOrderSupplierCreateResult,
  BackofficeOrderSupplierPayloadPreview,
  BackofficeProcurementRecommendation,
} from "@/features/backoffice/types/orders.types";
import type {
  BackofficeNovaPoshtaCounterpartyDetails,
  BackofficeNovaPoshtaLookupCounterparty,
  BackofficeNovaPoshtaLookupDeliveryDate,
  BackofficeNovaPoshtaLookupPackaging,
  BackofficeNovaPoshtaLookupSettlement,
  BackofficeNovaPoshtaLookupStreet,
  BackofficeNovaPoshtaLookupTimeInterval,
  BackofficeNovaPoshtaLookupWarehouse,
  BackofficeNovaPoshtaSenderProfile,
  BackofficeOrderNovaPoshtaWaybill,
  BackofficeOrderNovaPoshtaWaybillResponse,
} from "@/features/backoffice/types/nova-poshta.types";

import type { BackofficeListQuery } from "./backoffice-api.types";

export async function getBackofficeOrders(token: string, params?: BackofficeListQuery) {
  const data = await getJson<BackofficeOrderOperational[] | { results: BackofficeOrderOperational[]; count: number }>(
    "/backoffice/orders/",
    params,
    { token },
  );
  return normalizePaginatedListResponse(data);
}

export async function getBackofficeOrderDetail(token: string, orderId: string): Promise<BackofficeOrderOperational> {
  return getJson<BackofficeOrderOperational>(`/backoffice/orders/${orderId}/`, undefined, { token });
}

export async function confirmBackofficeOrder(
  token: string,
  payload: { order_id: string; operator_note?: string },
): Promise<{ order_id: string; status: string }> {
  return postJson<{ order_id: string; status: string }, typeof payload>("/backoffice/orders/actions/confirm/", payload, undefined, { token });
}

export async function markBackofficeOrderAwaitingProcurement(
  token: string,
  payload: { order_id: string; operator_note?: string },
): Promise<{ order_id: string; status: string }> {
  return postJson<{ order_id: string; status: string }, typeof payload>(
    "/backoffice/orders/actions/awaiting-procurement/",
    payload,
    undefined,
    { token },
  );
}

export async function reserveBackofficeOrder(
  token: string,
  payload: { order_id: string; item_ids?: string[]; operator_note?: string },
): Promise<{ order_id: string; status: string }> {
  return postJson<{ order_id: string; status: string }, typeof payload>("/backoffice/orders/actions/reserve/", payload, undefined, { token });
}

export async function markBackofficeOrderReadyToShip(
  token: string,
  payload: { order_id: string; operator_note?: string },
): Promise<{ order_id: string; status: string }> {
  return postJson<{ order_id: string; status: string }, typeof payload>("/backoffice/orders/actions/ready-to-ship/", payload, undefined, { token });
}

export async function cancelBackofficeOrder(
  token: string,
  payload: { order_id: string; reason_code: string; reason_note?: string; operator_note?: string },
): Promise<{ order_id: string; status: string }> {
  return postJson<{ order_id: string; status: string }, typeof payload>("/backoffice/orders/actions/cancel/", payload, undefined, { token });
}

export async function bulkConfirmBackofficeOrders(
  token: string,
  payload: { order_ids: string[]; operator_note?: string },
): Promise<{ updated: number }> {
  return postJson<{ updated: number }, typeof payload>("/backoffice/orders/actions/bulk-confirm/", payload, undefined, { token });
}

export async function bulkMarkAwaitingProcurementBackofficeOrders(
  token: string,
  payload: { order_ids: string[]; operator_note?: string },
): Promise<{ updated: number }> {
  return postJson<{ updated: number }, typeof payload>(
    "/backoffice/orders/actions/bulk-awaiting-procurement/",
    payload,
    undefined,
    { token },
  );
}

export async function deleteBackofficeOrder(
  token: string,
  payload: { order_id: string; operator_note?: string },
): Promise<BackofficeOrderDeleteResult> {
  return postJson<BackofficeOrderDeleteResult, typeof payload>("/backoffice/orders/actions/delete/", payload, undefined, { token });
}

export async function bulkDeleteBackofficeOrders(
  token: string,
  payload: { order_ids: string[]; operator_note?: string },
): Promise<BackofficeOrderBulkDeleteResult> {
  return postJson<BackofficeOrderBulkDeleteResult, typeof payload>("/backoffice/orders/actions/bulk-delete/", payload, undefined, { token });
}

export async function getBackofficeOrderSupplierPayload(
  token: string,
  payload: { order_id: string },
): Promise<BackofficeOrderSupplierPayloadPreview> {
  return postJson<BackofficeOrderSupplierPayloadPreview, typeof payload>("/backoffice/orders/supplier/gpl/payload/", payload, undefined, { token });
}

export async function createBackofficeGplSupplierOrder(
  token: string,
  payload: { order_id: string; products?: Array<{ id: number; count: number }>; test?: boolean },
): Promise<BackofficeOrderSupplierCreateResult> {
  return postJson<BackofficeOrderSupplierCreateResult, typeof payload>("/backoffice/orders/supplier/gpl/store/", payload, undefined, { token });
}

export async function cancelBackofficeGplSupplierOrder(
  token: string,
  payload: { order_id: string; supplier_order_id: number },
): Promise<BackofficeOrderSupplierCancelResult> {
  return postJson<BackofficeOrderSupplierCancelResult, typeof payload>("/backoffice/orders/supplier/gpl/cancel/", payload, undefined, { token });
}

export async function listBackofficeGplSupplierOrders(
  token: string,
  payload?: { page?: number },
): Promise<BackofficeGplOrdersResponse> {
  return postJson<BackofficeGplOrdersResponse, { page?: number }>("/backoffice/orders/supplier/gpl/all/", payload ?? {}, undefined, { token });
}

export async function getBackofficeGplSupplierOrder(
  token: string,
  supplierOrderId: number,
): Promise<BackofficeGplOrderResponse> {
  return postJson<BackofficeGplOrderResponse, Record<string, never>>(
    `/backoffice/orders/supplier/gpl/show/${supplierOrderId}/`,
    {},
    undefined,
    { token },
  );
}

export async function getBackofficeOrderItemSupplierRecommendation(token: string, itemId: string): Promise<BackofficeProcurementRecommendation> {
  return getJson<BackofficeProcurementRecommendation>(`/backoffice/orders/items/${itemId}/supplier-recommendation/`, undefined, { token });
}

export async function overrideBackofficeOrderItemSupplier(
  token: string,
  itemId: string,
  payload: { supplier_offer_id: string; operator_note?: string },
): Promise<BackofficeProcurementRecommendation> {
  return postJson<BackofficeProcurementRecommendation, typeof payload>(
    `/backoffice/orders/items/${itemId}/supplier-override/`,
    payload,
    undefined,
    { token },
  );
}

export async function listBackofficeNovaPoshtaSenderProfiles(
  token: string,
): Promise<BackofficeNovaPoshtaSenderProfile[]> {
  return getJson<BackofficeNovaPoshtaSenderProfile[]>("/backoffice/nova-poshta/senders/", undefined, { token });
}

export async function createBackofficeNovaPoshtaSenderProfile(
  token: string,
  payload: {
    name: string;
    sender_type: "private_person" | "fop" | "business";
    api_token: string;
    counterparty_ref: string;
    contact_ref: string;
    address_ref: string;
    city_ref: string;
    phone: string;
    contact_name?: string;
    organization_name?: string;
    edrpou?: string;
    is_active: boolean;
    is_default: boolean;
    raw_meta?: Record<string, unknown>;
  },
): Promise<BackofficeNovaPoshtaSenderProfile> {
  return postJson<BackofficeNovaPoshtaSenderProfile, typeof payload>(
    "/backoffice/nova-poshta/senders/",
    payload,
    undefined,
    { token },
  );
}

export async function updateBackofficeNovaPoshtaSenderProfile(
  token: string,
  senderId: string,
  payload: Record<string, unknown>,
): Promise<BackofficeNovaPoshtaSenderProfile> {
  return patchJson<BackofficeNovaPoshtaSenderProfile, Record<string, unknown>>(
    `/backoffice/nova-poshta/senders/${senderId}/`,
    payload,
    undefined,
    { token },
  );
}

export async function deleteBackofficeNovaPoshtaSenderProfile(
  token: string,
  senderId: string,
): Promise<void> {
  return deleteJson<void>(`/backoffice/nova-poshta/senders/${senderId}/`, undefined, { token });
}

export async function validateBackofficeNovaPoshtaSenderProfile(
  token: string,
  senderId: string,
): Promise<{ ok: boolean; message: string; options: Record<string, unknown> }> {
  return postJson<{ ok: boolean; message: string; options: Record<string, unknown> }, Record<string, never>>(
    `/backoffice/nova-poshta/senders/${senderId}/validate/`,
    {},
    undefined,
    { token },
  );
}

export async function lookupBackofficeNovaPoshtaSettlements(
  token: string,
  payload: { sender_profile_id: string; query: string; locale?: string },
): Promise<{ results: BackofficeNovaPoshtaLookupSettlement[] }> {
  return postJson<{ results: BackofficeNovaPoshtaLookupSettlement[] }, typeof payload>(
    "/backoffice/orders/waybill/lookups/settlements/",
    payload,
    undefined,
    { token },
  );
}

export async function lookupBackofficeNovaPoshtaCounterparties(
  token: string,
  payload: { sender_profile_id: string; query: string; counterparty_property?: string; locale?: string },
): Promise<{ results: BackofficeNovaPoshtaLookupCounterparty[] }> {
  return postJson<{ results: BackofficeNovaPoshtaLookupCounterparty[] }, typeof payload>(
    "/backoffice/orders/waybill/lookups/counterparties/",
    payload,
    undefined,
    { token },
  );
}

export async function lookupBackofficeNovaPoshtaCounterpartyDetails(
  token: string,
  payload: { sender_profile_id: string; counterparty_ref: string; counterparty_property?: string; locale?: string },
): Promise<{ result: BackofficeNovaPoshtaCounterpartyDetails }> {
  return postJson<{ result: BackofficeNovaPoshtaCounterpartyDetails }, typeof payload>(
    "/backoffice/orders/waybill/lookups/counterparty-details/",
    payload,
    undefined,
    { token },
  );
}

export async function lookupBackofficeNovaPoshtaStreets(
  token: string,
  payload: { sender_profile_id: string; settlement_ref: string; query: string; locale?: string },
): Promise<{ results: BackofficeNovaPoshtaLookupStreet[] }> {
  return postJson<{ results: BackofficeNovaPoshtaLookupStreet[] }, typeof payload>(
    "/backoffice/orders/waybill/lookups/streets/",
    payload,
    undefined,
    { token },
  );
}

export async function lookupBackofficeNovaPoshtaWarehouses(
  token: string,
  payload: { sender_profile_id: string; city_ref: string; query?: string; locale?: string; warehouse_type_ref?: string },
): Promise<{ results: BackofficeNovaPoshtaLookupWarehouse[] }> {
  return postJson<{ results: BackofficeNovaPoshtaLookupWarehouse[] }, typeof payload>(
    "/backoffice/orders/waybill/lookups/warehouses/",
    payload,
    undefined,
    { token },
  );
}

export async function lookupBackofficeNovaPoshtaPackings(
  token: string,
  payload: { sender_profile_id: string; length_mm?: number; width_mm?: number; height_mm?: number; locale?: string },
): Promise<{ results: BackofficeNovaPoshtaLookupPackaging[] }> {
  return postJson<{ results: BackofficeNovaPoshtaLookupPackaging[] }, typeof payload>(
    "/backoffice/orders/waybill/lookups/packings/",
    payload,
    undefined,
    { token },
  );
}

export async function lookupBackofficeNovaPoshtaDeliveryDate(
  token: string,
  payload: { sender_profile_id: string; recipient_city_ref: string; delivery_type: "warehouse" | "postomat" | "address"; date_time?: string },
): Promise<{ result: BackofficeNovaPoshtaLookupDeliveryDate }> {
  return postJson<{ result: BackofficeNovaPoshtaLookupDeliveryDate }, typeof payload>(
    "/backoffice/orders/waybill/lookups/delivery-date/",
    payload,
    undefined,
    { token },
  );
}

export async function lookupBackofficeNovaPoshtaTimeIntervals(
  token: string,
  payload: { sender_profile_id: string; recipient_city_ref: string; date_time?: string },
): Promise<{ results: BackofficeNovaPoshtaLookupTimeInterval[] }> {
  return postJson<{ results: BackofficeNovaPoshtaLookupTimeInterval[] }, typeof payload>(
    "/backoffice/orders/waybill/lookups/time-intervals/",
    payload,
    undefined,
    { token },
  );
}

type WaybillUpsertPayload = {
  sender_profile_id: string;
  delivery_type: "warehouse" | "postomat" | "address";
  payer_type?: "Sender" | "Recipient" | "ThirdPerson";
  payment_method?: "Cash" | "NonCash";
  cargo_type?: "Cargo" | "Parcel" | "Documents" | "Pallet" | "TiresWheels";
  description?: string;
  recipient_city_ref: string;
  recipient_city_label?: string;
  recipient_address_ref?: string;
  recipient_address_label?: string;
  recipient_counterparty_ref?: string;
  recipient_contact_ref?: string;
  recipient_street_ref?: string;
  recipient_street_label?: string;
  recipient_house?: string;
  recipient_apartment?: string;
  recipient_name: string;
  recipient_phone: string;
  seats_amount?: number;
  weight: string;
  volume_general?: string;
  pack_ref?: string;
  pack_refs?: string[];
  volumetric_width?: string;
  volumetric_length?: string;
  volumetric_height?: string;
  cost: string;
  afterpayment_amount?: string;
  saturday_delivery?: boolean;
  local_express?: boolean;
  preferred_delivery_date?: string;
  time_interval?: "CityDeliveryTimeInterval1" | "CityDeliveryTimeInterval2" | "CityDeliveryTimeInterval3" | "CityDeliveryTimeInterval4" | "";
  info_reg_client_barcodes?: string;
  accompanying_documents?: string;
  red_box_barcode?: string;
  number_of_floors_lifting?: string;
  number_of_floors_descent?: string;
  forwarding_count?: string;
  delivery_by_hand?: boolean;
  delivery_by_hand_recipients?: string;
  special_cargo?: boolean;
};

export async function getBackofficeOrderWaybill(
  token: string,
  orderId: string,
): Promise<BackofficeOrderNovaPoshtaWaybillResponse> {
  return getJson<BackofficeOrderNovaPoshtaWaybillResponse>(`/backoffice/orders/${orderId}/waybill/`, undefined, { token });
}

export async function createBackofficeOrderWaybill(
  token: string,
  orderId: string,
  payload: WaybillUpsertPayload,
): Promise<BackofficeOrderNovaPoshtaWaybill> {
  return postJson<BackofficeOrderNovaPoshtaWaybill, WaybillUpsertPayload>(
    `/backoffice/orders/${orderId}/waybill/create/`,
    payload,
    undefined,
    { token },
  );
}

export async function updateBackofficeOrderWaybill(
  token: string,
  orderId: string,
  payload: WaybillUpsertPayload,
): Promise<BackofficeOrderNovaPoshtaWaybill> {
  return postJson<BackofficeOrderNovaPoshtaWaybill, WaybillUpsertPayload>(
    `/backoffice/orders/${orderId}/waybill/update/`,
    payload,
    undefined,
    { token },
  );
}

export async function syncBackofficeOrderWaybill(
  token: string,
  orderId: string,
): Promise<BackofficeOrderNovaPoshtaWaybill> {
  return postJson<BackofficeOrderNovaPoshtaWaybill, Record<string, never>>(
    `/backoffice/orders/${orderId}/waybill/sync/`,
    {},
    undefined,
    { token },
  );
}

export async function deleteBackofficeOrderWaybill(
  token: string,
  orderId: string,
): Promise<BackofficeOrderNovaPoshtaWaybill> {
  return postJson<BackofficeOrderNovaPoshtaWaybill, Record<string, never>>(
    `/backoffice/orders/${orderId}/waybill/delete/`,
    {},
    undefined,
    { token },
  );
}

export async function printBackofficeOrderWaybill(
  token: string,
  orderId: string,
  format: "html" | "pdf",
): Promise<Blob> {
  const url = `${siteConfig.apiBaseUrl}/backoffice/orders/${orderId}/waybill/print/?format=${format}`;
  const response = await fetch(url, {
    method: "GET",
    headers: {
      Authorization: `Token ${token}`,
    },
    cache: "no-store",
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Unable to load print form.");
  }
  return response.blob();
}
