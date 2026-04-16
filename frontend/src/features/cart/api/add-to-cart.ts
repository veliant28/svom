import { postJson } from "@/shared/api/http-client";

import type { Cart } from "@/features/commerce/types";

export async function addToCart(token: string, productId: string, quantity = 1): Promise<Cart> {
  return postJson<Cart, { product_id: string; quantity: number }>(
    "/commerce/cart/items/",
    { product_id: productId, quantity },
    undefined,
    { token },
  );
}
