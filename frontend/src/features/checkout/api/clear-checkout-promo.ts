import { postJson } from "@/shared/api/http-client";

import type { CheckoutPreviewResponse, Order } from "@/features/commerce/types";

export async function clearCheckoutPromo(
  token: string,
  payload: { delivery_method?: Order["delivery_method"] },
): Promise<CheckoutPreviewResponse> {
  return postJson<CheckoutPreviewResponse, typeof payload>("/commerce/checkout/promo/clear/", payload, undefined, { token });
}
