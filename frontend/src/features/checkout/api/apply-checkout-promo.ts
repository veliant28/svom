import { postJson } from "@/shared/api/http-client";

import type { CheckoutPreviewResponse, Order } from "@/features/commerce/types";

export async function applyCheckoutPromo(
  token: string,
  payload: { promo_code: string; delivery_method?: Order["delivery_method"] },
): Promise<CheckoutPreviewResponse> {
  return postJson<CheckoutPreviewResponse, typeof payload>("/commerce/checkout/promo/apply/", payload, undefined, { token });
}
