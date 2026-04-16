import { deleteJson } from "@/shared/api/http-client";

export async function removeWishlistItem(token: string, itemId: string): Promise<void> {
  await deleteJson<void>(`/commerce/wishlist/items/${itemId}/`, undefined, { token });
}
