import { getJson } from "@/shared/api/http-client";

import type { CatalogFilters, ProductDetail } from "../types";

type ProductDetailParams = Pick<CatalogFilters, "car_modification" | "garage_vehicle" | "modification">;

export async function getProductDetail(slug: string, locale?: string, params: ProductDetailParams = {}): Promise<ProductDetail> {
  return getJson<ProductDetail>(`/catalog/products/${slug}/`, { ...params, locale });
}
