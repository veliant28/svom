import { getJson } from "@/shared/api/http-client";

import type { CatalogFilters, ProductFitmentOptions } from "../types";

type ProductFitmentOptionsParams = Pick<CatalogFilters, "car_modification" | "garage_vehicle"> & {
  make?: string;
};

export async function getProductFitmentOptions(
  slug: string,
  locale?: string,
  params: ProductFitmentOptionsParams = {},
): Promise<ProductFitmentOptions> {
  return getJson<ProductFitmentOptions>(`/catalog/products/${slug}/fitment-options/`, { ...params, locale });
}
