import { getJson } from "@/shared/api/http-client";

import type { CheckoutMethods } from "@/features/checkout/types/methods";

export async function getCheckoutMethods(token: string): Promise<CheckoutMethods> {
  return getJson<CheckoutMethods>("/commerce/checkout/methods/", undefined, { token });
}
