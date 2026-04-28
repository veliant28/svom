import { getJson, patchJson } from "@/shared/api/http-client";

import type { CheckoutMethodSettings } from "@/features/backoffice/types/checkout-method-settings.types";

export async function getCheckoutMethodSettings(token: string): Promise<CheckoutMethodSettings> {
  return getJson<CheckoutMethodSettings>("/backoffice/payments/checkout-methods/", undefined, { token });
}

export async function updateCheckoutMethodSettings(
  token: string,
  payload: Partial<CheckoutMethodSettings>,
): Promise<CheckoutMethodSettings> {
  return patchJson<CheckoutMethodSettings, Partial<CheckoutMethodSettings>>(
    "/backoffice/payments/checkout-methods/",
    payload,
    undefined,
    { token },
  );
}
