import { getJson, isApiRequestError } from "@/shared/api/http-client";

import type { CatalogFilters, ProductDetail } from "../types";

type ProductDetailParams = Pick<
  CatalogFilters,
  "vehicle_id" | "passanger_car_id" | "garage_vehicle" | "modification"
>;

export async function getProductDetail(slug: string, locale?: string, params: ProductDetailParams = {}): Promise<ProductDetail> {
  const request = () => getJson<ProductDetail>(`/catalog/products/${slug}`, { ...params, locale });

  try {
    return await request();
  } catch (error: unknown) {
    if (isApiRequestError(error) && error.isNetworkError && error.isTimeout) {
      await new Promise((resolve) => {
        setTimeout(resolve, 400);
      });
      return request();
    }
    throw error;
  }
}
