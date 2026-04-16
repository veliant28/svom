import { patchJson } from "@/shared/api/http-client";

import type { Cart } from "@/features/commerce/types";

export async function updateCartItem(token: string, itemId: string, quantity: number): Promise<Cart> {
  return patchJson<Cart, { quantity: number }>(
    `/commerce/cart/items/${itemId}/`,
    { quantity },
    undefined,
    { token },
  );
}
