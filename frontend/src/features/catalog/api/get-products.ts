import { getJson } from "@/shared/api/http-client";
import { normalizePaginatedListResponse, type ListResponse } from "@/shared/api/normalize-list-response";

import type { CatalogFilters, CatalogProduct, PaginatedResponse } from "../types";

export type GetProductsParams = CatalogFilters & {
  locale?: string;
  page?: number;
  pageSize?: number;
};

type CatalogProductsResponse = ListResponse<CatalogProduct>;

export async function getProducts(params: GetProductsParams = {}): Promise<PaginatedResponse<CatalogProduct>> {
  const data = await getJson<CatalogProductsResponse>("/catalog/products/", {
    locale: params.locale,
    page: params.page,
    page_size: params.pageSize,
    q: params.q,
    brand: params.brand,
    category: params.category,
    min_price: params.min_price,
    max_price: params.max_price,
    is_featured: params.is_featured,
    is_new: params.is_new,
    is_bestseller: params.is_bestseller,
    modification: params.modification,
    garage_vehicle: params.garage_vehicle,
    fitment: params.fitment,
  });

  return normalizePaginatedListResponse(data);
}
