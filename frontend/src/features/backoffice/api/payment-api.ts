import { getJson, patchJson, postJson } from "@/shared/api/http-client";

import type {
  BackofficeMonobankPaymentAction,
  BackofficeMonobankPaymentActionResult,
  BackofficeOrderPayment,
} from "@/features/backoffice/types/orders.types";
import type {
  BackofficeMonobankConnectionCheck,
  BackofficeMonobankCurrencyResponse,
  BackofficeMonobankSettings,
  BackofficeNovaPaySettings,
} from "@/features/backoffice/types/payment.types";

export async function getBackofficeMonobankSettings(token: string): Promise<BackofficeMonobankSettings> {
  return getJson<BackofficeMonobankSettings>("/backoffice/payments/monobank/settings/", undefined, { token });
}

export async function updateBackofficeMonobankSettings(
  token: string,
  payload: Partial<{
    is_enabled: boolean;
    merchant_token: string;
    widget_key_id: string;
    widget_private_key: string;
  }>,
): Promise<BackofficeMonobankSettings> {
  return patchJson<BackofficeMonobankSettings, Record<string, unknown>>(
    "/backoffice/payments/monobank/settings/",
    payload,
    undefined,
    { token },
  );
}

export async function testBackofficeMonobankConnection(token: string): Promise<BackofficeMonobankConnectionCheck> {
  return postJson<BackofficeMonobankConnectionCheck, Record<string, never>>(
    "/backoffice/payments/monobank/test-connection/",
    {},
    undefined,
    { token },
  );
}

export async function getBackofficeMonobankCurrency(
  token: string,
  params?: { refresh?: boolean },
): Promise<BackofficeMonobankCurrencyResponse> {
  return getJson<BackofficeMonobankCurrencyResponse>(
    "/backoffice/payments/monobank/currency/",
    params,
    { token },
  );
}

export async function refreshBackofficeOrderPayment(token: string, orderId: string): Promise<BackofficeOrderPayment> {
  return postJson<BackofficeOrderPayment, Record<string, never>>(
    `/backoffice/orders/${orderId}/payment/refresh/`,
    {},
    undefined,
    { token },
  );
}

export async function runBackofficeOrderMonobankPaymentAction(
  token: string,
  orderId: string,
  payload: { action: BackofficeMonobankPaymentAction; amount?: number },
): Promise<BackofficeMonobankPaymentActionResult> {
  return postJson<BackofficeMonobankPaymentActionResult, typeof payload>(
    `/backoffice/orders/${orderId}/payment/monobank/action/`,
    payload,
    undefined,
    { token },
  );
}

export async function getBackofficeNovaPaySettings(token: string): Promise<BackofficeNovaPaySettings> {
  return getJson<BackofficeNovaPaySettings>("/backoffice/payments/novapay/settings/", undefined, { token });
}

export async function updateBackofficeNovaPaySettings(
  token: string,
  payload: Partial<{
    is_enabled: boolean;
    merchant_id: string;
    api_token: string;
  }>,
): Promise<BackofficeNovaPaySettings> {
  return patchJson<BackofficeNovaPaySettings, Record<string, unknown>>(
    "/backoffice/payments/novapay/settings/",
    payload,
    undefined,
    { token },
  );
}
