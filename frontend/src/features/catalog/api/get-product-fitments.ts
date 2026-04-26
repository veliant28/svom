import { getJson } from "@/shared/api/http-client";

import type { CatalogFilters, ProductFitmentRowsResponse } from "../types";

type ProductFitmentRowsParams = Pick<CatalogFilters, "car_modification" | "garage_vehicle"> & {
  make?: string;
  model?: string;
  limit?: number;
  offset?: number;
};

export async function getProductFitments(
  slug: string,
  locale?: string,
  params: ProductFitmentRowsParams = {},
): Promise<ProductFitmentRowsResponse> {
  return getJson<ProductFitmentRowsResponse>(`/catalog/products/${slug}/fitments/`, { ...params, locale });
}
