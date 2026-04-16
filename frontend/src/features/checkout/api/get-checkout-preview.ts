import { getJson } from "@/shared/api/http-client";

import type { CheckoutPreviewResponse, Order } from "@/features/commerce/types";

export async function getCheckoutPreview(token: string, deliveryMethod?: Order["delivery_method"]): Promise<CheckoutPreviewResponse> {
  return getJson<CheckoutPreviewResponse>(
    "/commerce/checkout/preview/",
    {
      delivery_method: deliveryMethod,
    },
    { token },
  );
}
