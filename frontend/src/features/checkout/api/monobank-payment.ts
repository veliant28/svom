import { getJson } from "@/shared/api/http-client";

import type { MonobankSelectorWidgetResponse, MonobankWidgetResponse } from "@/features/checkout/types/payment";

export async function getCheckoutMonobankWidget(token: string, orderId: string): Promise<MonobankWidgetResponse> {
  return getJson<MonobankWidgetResponse>(`/commerce/checkout/orders/${orderId}/monobank-widget/`, undefined, { token });
}

export async function getCheckoutMonobankSelectorWidget(token: string): Promise<MonobankSelectorWidgetResponse> {
  return getJson<MonobankSelectorWidgetResponse>("/commerce/checkout/monobank-selector-widget/", undefined, { token });
}
