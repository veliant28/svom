import { getJson } from "@/shared/api/http-client";
import { normalizeListResponse, type ListResponse } from "@/shared/api/normalize-list-response";

import type { CatalogFilters, CatalogProduct } from "../types";

type GetHomePopularProductsParams = Pick<CatalogFilters, "vehicle_id" | "passanger_car_id" | "garage_vehicle" | "fitment"> & {
  locale?: string;
};

export async function getHomePopularProducts(
  params: GetHomePopularProductsParams = {},
): Promise<CatalogProduct[]> {
  const data = await getJson<ListResponse<CatalogProduct>>("/catalog/home/popular-products/", {
    locale: params.locale,
    vehicle_id: params.vehicle_id,
    passanger_car_id: params.passanger_car_id,
    garage_vehicle: params.garage_vehicle,
    fitment: params.fitment,
  });
  return normalizeListResponse(data);
}

