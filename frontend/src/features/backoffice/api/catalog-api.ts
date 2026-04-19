import { deleteJson, getJson, patchJson, postJson } from "@/shared/api/http-client";
import { normalizePaginatedListResponse } from "@/shared/api/normalize-list-response";

import type { BackofficeCatalogBrand, BackofficeCatalogCategory, BackofficeCatalogProduct } from "@/features/backoffice/types/backoffice";

import type { BackofficeListQuery } from "./backoffice-api.types";

export async function getBackofficeCatalogBrands(token: string, params?: BackofficeListQuery) {
  const data = await getJson<BackofficeCatalogBrand[] | { results: BackofficeCatalogBrand[]; count: number }>(
    "/backoffice/brands/",
    params,
    { token },
  );
  return normalizePaginatedListResponse(data);
}

export async function createBackofficeCatalogBrand(
  token: string,
  payload: Partial<BackofficeCatalogBrand>,
): Promise<BackofficeCatalogBrand> {
  return postJson<BackofficeCatalogBrand, typeof payload>("/backoffice/brands/", payload, undefined, { token });
}

export async function updateBackofficeCatalogBrand(
  token: string,
  brandId: string,
  payload: Partial<BackofficeCatalogBrand>,
): Promise<BackofficeCatalogBrand> {
  return patchJson<BackofficeCatalogBrand, typeof payload>(`/backoffice/brands/${brandId}/`, payload, undefined, { token });
}

export async function deleteBackofficeCatalogBrand(
  token: string,
  brandId: string,
): Promise<void> {
  return deleteJson<void>(`/backoffice/brands/${brandId}/`, undefined, { token });
}

export async function getBackofficeCatalogCategories(token: string, params?: BackofficeListQuery) {
  const data = await getJson<BackofficeCatalogCategory[] | { results: BackofficeCatalogCategory[]; count: number }>(
    "/backoffice/categories/",
    params,
    { token },
  );
  return normalizePaginatedListResponse(data);
}

export async function createBackofficeCatalogCategory(
  token: string,
  payload: Partial<BackofficeCatalogCategory>,
): Promise<BackofficeCatalogCategory> {
  return postJson<BackofficeCatalogCategory, typeof payload>("/backoffice/categories/", payload, undefined, { token });
}

export async function updateBackofficeCatalogCategory(
  token: string,
  categoryId: string,
  payload: Partial<BackofficeCatalogCategory>,
): Promise<BackofficeCatalogCategory> {
  return patchJson<BackofficeCatalogCategory, typeof payload>(`/backoffice/categories/${categoryId}/`, payload, undefined, { token });
}

export async function deleteBackofficeCatalogCategory(
  token: string,
  categoryId: string,
): Promise<void> {
  return deleteJson<void>(`/backoffice/categories/${categoryId}/`, undefined, { token });
}

export async function getBackofficeCatalogProducts(token: string, params?: BackofficeListQuery) {
  const data = await getJson<BackofficeCatalogProduct[] | { results: BackofficeCatalogProduct[]; count: number }>(
    "/backoffice/products/",
    params,
    { token },
  );
  return normalizePaginatedListResponse(data);
}

export async function createBackofficeCatalogProduct(
  token: string,
  payload: Partial<BackofficeCatalogProduct>,
): Promise<BackofficeCatalogProduct> {
  return postJson<BackofficeCatalogProduct, typeof payload>("/backoffice/products/", payload, undefined, { token });
}

export async function updateBackofficeCatalogProduct(
  token: string,
  productId: string,
  payload: Partial<BackofficeCatalogProduct>,
): Promise<BackofficeCatalogProduct> {
  return patchJson<BackofficeCatalogProduct, typeof payload>(`/backoffice/products/${productId}/`, payload, undefined, { token });
}

export async function deleteBackofficeCatalogProduct(
  token: string,
  productId: string,
): Promise<void> {
  return deleteJson<void>(`/backoffice/products/${productId}/`, undefined, { token });
}

export async function runReindexProductsAction(
  token: string,
  payload: { product_ids: string[]; dispatch_async?: boolean },
): Promise<{ mode: string; queued: number; summary?: Record<string, unknown> }> {
  return postJson<{ mode: string; queued: number; summary?: Record<string, unknown> }, typeof payload>(
    "/backoffice/actions/reindex-products/",
    payload,
    undefined,
    { token },
  );
}

export async function runBulkMoveProductsCategoryAction(
  token: string,
  payload: {
    product_ids: string[];
    category_id: string;
    update_import_rules?: boolean;
  },
): Promise<{
  target_category_id: string;
  products_requested: number;
  products_found: number;
  products_updated: number;
  raw_offers_total: number;
  raw_offers_updated: number;
  update_import_rules: boolean;
}> {
  return postJson<
    {
      target_category_id: string;
      products_requested: number;
      products_found: number;
      products_updated: number;
      raw_offers_total: number;
      raw_offers_updated: number;
      update_import_rules: boolean;
    },
    typeof payload
  >(
    "/backoffice/actions/bulk-move-products-category/",
    payload,
    undefined,
    { token },
  );
}
