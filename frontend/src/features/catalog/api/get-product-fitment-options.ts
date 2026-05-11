import { getJson } from "@/shared/api/http-client";

import type { CatalogFilters, ProductFitmentOptions } from "../types";

type ProductFitmentOptionsParams = Pick<
  CatalogFilters,
  "vehicle_id" | "passanger_car_id" | "garage_vehicle"
> & {
  make?: string;
  model?: string;
  modification?: string;
};

export async function getProductFitmentOptions(
  slug: string,
  locale?: string,
  params: ProductFitmentOptionsParams = {},
): Promise<ProductFitmentOptions> {
  return getJson<ProductFitmentOptions>(`/catalog/products/${slug}/compatibility/options/`, { ...params, locale });
}
