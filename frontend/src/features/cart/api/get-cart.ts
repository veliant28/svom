import { getJson } from "@/shared/api/http-client";

import type { Cart } from "@/features/commerce/types";

export async function getCart(token: string): Promise<Cart> {
  return getJson<Cart>("/commerce/cart/", undefined, { token });
}
