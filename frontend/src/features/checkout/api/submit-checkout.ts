import { postJson } from "@/shared/api/http-client";

import type { Order } from "@/features/commerce/types";

export type CheckoutSubmitPayload = {
  contact_full_name: string;
  contact_phone: string;
  contact_email: string;
  delivery_method: Order["delivery_method"];
  delivery_address?: string;
  delivery_snapshot?: Record<string, unknown>;
  payment_method: Order["payment_method"];
  customer_comment?: string;
  promo_code?: string;
};

export async function submitCheckout(token: string, payload: CheckoutSubmitPayload): Promise<Order> {
  return postJson<Order, CheckoutSubmitPayload>("/commerce/checkout/submit/", payload, undefined, { token });
}
