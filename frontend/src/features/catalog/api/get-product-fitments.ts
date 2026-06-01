import { getJson } from "@/shared/api/http-client";

import type { CatalogFilters, ProductFitmentRowsResponse } from "../types";

type ProductFitmentRowsParams = Pick<
  CatalogFilters,
  "vehicle_id" | "passanger_car_id" | "garage_vehicle"
> & {
  make?: string;
  model?: string;
  modification?: string;
  limit?: number;
  offset?: number;
};

export async function getProductFitments(
  slug: string,
  locale?: string,
  params: ProductFitmentRowsParams = {},
): Promise<ProductFitmentRowsResponse> {
  return getJson<ProductFitmentRowsResponse>(`/catalog/products/${slug}/fitments`, { ...params, locale });
}
