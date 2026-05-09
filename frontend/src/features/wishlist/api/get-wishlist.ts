import { getJson } from "@/shared/api/http-client";

import type { CatalogFilters } from "@/features/catalog/types";
import type { WishlistItem } from "@/features/commerce/types";

type WishlistQueryParams = Pick<
  CatalogFilters,
  "vehicle_id" | "passanger_car_id" | "garage_vehicle" | "car_modification" | "fitment"
> & {
  locale?: string;
};

export async function getWishlist(token: string, params?: WishlistQueryParams): Promise<WishlistItem[]> {
  return getJson<WishlistItem[]>("/commerce/wishlist/", params, { token });
}
