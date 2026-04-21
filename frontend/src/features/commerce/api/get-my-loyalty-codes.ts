import { getJson } from "@/shared/api/http-client";

import type { LoyaltyPromoCode } from "@/features/commerce/types";

export async function getMyLoyaltyCodes(token: string): Promise<LoyaltyPromoCode[]> {
  return getJson<LoyaltyPromoCode[]>("/commerce/loyalty/my-codes/", undefined, { token });
}
