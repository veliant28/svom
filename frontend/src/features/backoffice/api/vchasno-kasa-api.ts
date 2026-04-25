import { getJson, patchJson, postJson } from "@/shared/api/http-client";

import type {
  BackofficeOrderReceiptActionResult,
  BackofficeVchasnoKasaConnectionCheck,
  BackofficeVchasnoKasaSettings,
  BackofficeVchasnoKasaShiftStatus,
  BackofficeVchasnoReceiptList,
} from "@/features/backoffice/types/vchasno-kasa.types";

export async function getBackofficeVchasnoKasaSettings(token: string): Promise<BackofficeVchasnoKasaSettings> {
  return getJson<BackofficeVchasnoKasaSettings>("/backoffice/vchasno-kasa/settings/", undefined, { token });
}

export async function updateBackofficeVchasnoKasaSettings(
  token: string,
  payload: Partial<{
    is_enabled: boolean;
    api_token: string;
    fiscal_api_token: string;
    rro_fn: string;
    default_payment_type: number;
    default_tax_group: string;
    selected_payment_methods: string[];
    selected_tax_groups: string[];
    auto_issue_on_completed: boolean;
    send_customer_email: boolean;
  }>,
): Promise<BackofficeVchasnoKasaSettings> {
  return patchJson<BackofficeVchasnoKasaSettings, typeof payload>("/backoffice/vchasno-kasa/settings/", payload, undefined, { token });
}

export async function testBackofficeVchasnoKasaConnection(token: string): Promise<BackofficeVchasnoKasaConnectionCheck> {
  return postJson<BackofficeVchasnoKasaConnectionCheck, Record<string, never>>(
    "/backoffice/vchasno-kasa/test-connection/",
    {},
    undefined,
    { token },
  );
}

export async function getBackofficeVchasnoKasaShiftStatus(token: string): Promise<BackofficeVchasnoKasaShiftStatus> {
  return getJson<BackofficeVchasnoKasaShiftStatus>("/backoffice/vchasno-kasa/shift-status/", undefined, { token });
}

export async function openBackofficeVchasnoKasaShift(token: string): Promise<BackofficeVchasnoKasaShiftStatus> {
  return postJson<BackofficeVchasnoKasaShiftStatus, Record<string, never>>(
    "/backoffice/vchasno-kasa/open-shift/",
    {},
    undefined,
    { token },
  );
}

export async function closeBackofficeVchasnoKasaShift(token: string): Promise<BackofficeVchasnoKasaShiftStatus> {
  return postJson<BackofficeVchasnoKasaShiftStatus, Record<string, never>>(
    "/backoffice/vchasno-kasa/close-shift/",
    {},
    undefined,
    { token },
  );
}

export async function listBackofficeVchasnoReceipts(token: string): Promise<BackofficeVchasnoReceiptList> {
  return getJson<BackofficeVchasnoReceiptList>("/backoffice/vchasno-kasa/receipts/", undefined, { token });
}

export async function issueBackofficeOrderReceipt(token: string, orderId: string): Promise<BackofficeOrderReceiptActionResult> {
  return postJson<BackofficeOrderReceiptActionResult, Record<string, never>>(
    `/backoffice/orders/${orderId}/receipt/vchasno-kasa/issue/`,
    {},
    undefined,
    { token },
  );
}

export async function syncBackofficeOrderReceipt(token: string, orderId: string): Promise<BackofficeOrderReceiptActionResult> {
  return postJson<BackofficeOrderReceiptActionResult, Record<string, never>>(
    `/backoffice/orders/${orderId}/receipt/vchasno-kasa/sync/`,
    {},
    undefined,
    { token },
  );
}

export async function getBackofficeOrderReceiptOpenUrl(token: string, orderId: string): Promise<{ url: string }> {
  return getJson<{ url: string }>(`/backoffice/orders/${orderId}/receipt/vchasno-kasa/open/`, { mode: "json" }, { token });
}
