import { getJson } from "@/shared/api/http-client";

import type { WishlistItem } from "@/features/commerce/types";

export async function getWishlist(token: string): Promise<WishlistItem[]> {
  return getJson<WishlistItem[]>("/commerce/wishlist/", undefined, { token });
}
