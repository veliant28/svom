import { postJson } from "@/shared/api/http-client";

import type { WishlistItem } from "@/features/commerce/types";

export async function addWishlistItem(token: string, productId: string): Promise<WishlistItem> {
  return postJson<WishlistItem, { product_id: string }>(
    "/commerce/wishlist/items/",
    { product_id: productId },
    undefined,
    { token },
  );
}
