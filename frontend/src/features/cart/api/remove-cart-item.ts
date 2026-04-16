import { deleteJson } from "@/shared/api/http-client";

import type { Cart } from "@/features/commerce/types";

export async function removeCartItem(token: string, itemId: string): Promise<Cart> {
  return deleteJson<Cart>(`/commerce/cart/items/${itemId}/`, undefined, { token });
}
