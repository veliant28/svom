import { getJson, patchJson, postJson } from "@/shared/api/http-client";
import { normalizePaginatedListResponse } from "@/shared/api/normalize-list-response";

import type {
  BackofficeActionResponse,
  BackofficeImportError,
  BackofficeImportRun,
  BackofficeSupplierListItem,
  BackofficeSupplierOffer,
  BackofficeSupplierPriceList,
  BackofficeSupplierPriceListParams,
  BackofficeSupplierPublishMappedResult,
  BackofficeSupplierWorkspace,
  BackofficeUtrBrandImportSummary,
} from "@/features/backoffice/types/backoffice";

import type { BackofficeListQuery } from "./backoffice-api.types";

export async function getBackofficeSuppliers(token: string): Promise<BackofficeSupplierListItem[]> {
  return getJson<BackofficeSupplierListItem[]>("/backoffice/suppliers/", undefined, { token });
}

export async function getBackofficeSupplierWorkspace(token: string, code: string): Promise<BackofficeSupplierWorkspace> {
  return getJson<BackofficeSupplierWorkspace>(`/backoffice/suppliers/${code}/workspace/`, undefined, { token });
}

export async function updateBackofficeSupplierSettings(
  token: string,
  code: string,
  payload: Partial<{
    login: string;
    password: string;
    browser_fingerprint: string;
    is_enabled: boolean;
  }>,
): Promise<BackofficeSupplierWorkspace> {
  return patchJson<BackofficeSupplierWorkspace, typeof payload>(
    `/backoffice/suppliers/${code}/settings/`,
    payload,
    undefined,
    { token },
  );
}

export async function obtainBackofficeSupplierToken(token: string, code: string): Promise<BackofficeSupplierWorkspace> {
  return postJson<BackofficeSupplierWorkspace, Record<string, never>>(
    `/backoffice/suppliers/${code}/token/obtain/`,
    {},
    undefined,
    { token },
  );
}

export async function refreshBackofficeSupplierToken(token: string, code: string): Promise<BackofficeSupplierWorkspace> {
  return postJson<BackofficeSupplierWorkspace, Record<string, never>>(
    `/backoffice/suppliers/${code}/token/refresh/`,
    {},
    undefined,
    { token },
  );
}

export async function checkBackofficeSupplierConnection(
  token: string,
  code: string,
): Promise<{ ok: boolean; details: Record<string, unknown>; workspace: BackofficeSupplierWorkspace }> {
  return postJson<{ ok: boolean; details: Record<string, unknown>; workspace: BackofficeSupplierWorkspace }, Record<string, never>>(
    `/backoffice/suppliers/${code}/connection/check/`,
    {},
    undefined,
    { token },
  );
}

export async function runBackofficeSupplierImport(
  token: string,
  code: string,
  payload: {
    dry_run?: boolean;
    dispatch_async?: boolean;
  },
): Promise<BackofficeActionResponse> {
  return postJson<BackofficeActionResponse, typeof payload>(`/backoffice/suppliers/${code}/import/run/`, payload, undefined, { token });
}

export async function publishBackofficeSupplierMappedProducts(
  token: string,
  code: string,
  payload: {
    include_needs_review?: boolean;
    dry_run?: boolean;
    reprice_after_publish?: boolean;
  } = {},
): Promise<{ mode: "sync"; result: BackofficeSupplierPublishMappedResult }> {
  return postJson<{ mode: "sync"; result: BackofficeSupplierPublishMappedResult }, typeof payload>(
    `/backoffice/suppliers/${code}/products/publish-mapped/`,
    payload,
    undefined,
    { token },
  );
}

export async function syncBackofficeSupplierPrices(
  token: string,
  code: string,
  payload?: {
    dispatch_async?: boolean;
  },
): Promise<BackofficeActionResponse> {
  return postJson<BackofficeActionResponse, { dispatch_async?: boolean }>(
    `/backoffice/suppliers/${code}/prices/sync/`,
    payload ?? {},
    undefined,
    { token },
  );
}

export async function importBackofficeUtrBrands(
  token: string,
): Promise<{ imported_count: number; summary: BackofficeUtrBrandImportSummary; workspace: BackofficeSupplierWorkspace }> {
  return postJson<{ imported_count: number; summary: BackofficeUtrBrandImportSummary; workspace: BackofficeSupplierWorkspace }, Record<string, never>>(
    "/backoffice/suppliers/utr/brands/import/",
    {},
    undefined,
    { token },
  );
}

export async function getBackofficeSupplierPrices(token: string, code: string, params?: BackofficeListQuery) {
  const data = await getJson<BackofficeSupplierOffer[] | { results: BackofficeSupplierOffer[]; count: number }>(
    `/backoffice/suppliers/${code}/prices/`,
    params,
    { token },
  );
  return normalizePaginatedListResponse(data);
}

export async function getBackofficeSupplierPriceLists(token: string, code: string, params?: BackofficeListQuery) {
  return getJson<{ count: number; results: BackofficeSupplierPriceList[] }>(
    `/backoffice/suppliers/${code}/price-lists/`,
    params,
    { token },
  );
}

export async function getBackofficeSupplierPriceListParams(token: string, code: string): Promise<BackofficeSupplierPriceListParams> {
  return getJson<BackofficeSupplierPriceListParams>(`/backoffice/suppliers/${code}/price-lists/params/`, undefined, { token });
}

export async function requestBackofficeSupplierPriceList(
  token: string,
  code: string,
  payload: Partial<{
    format: string;
    in_stock: boolean;
    show_scancode: boolean;
    utr_article: boolean;
    visible_brands: number[];
    categories: string[];
    models_filter: string[];
  }>,
): Promise<{ price_list: BackofficeSupplierPriceList }> {
  return postJson<{ price_list: BackofficeSupplierPriceList }, typeof payload>(
    `/backoffice/suppliers/${code}/price-lists/request/`,
    payload,
    undefined,
    { token },
  );
}

export async function downloadBackofficeSupplierPriceList(
  token: string,
  code: string,
  priceListId: string,
): Promise<{ price_list: BackofficeSupplierPriceList }> {
  return postJson<{ price_list: BackofficeSupplierPriceList }, Record<string, never>>(
    `/backoffice/suppliers/${code}/price-lists/${priceListId}/download/`,
    {},
    undefined,
    { token },
  );
}

export async function deleteBackofficeSupplierPriceList(
  token: string,
  code: string,
  priceListId: string,
): Promise<{
  deleted: boolean;
  deleted_remote: boolean;
  deleted_file: boolean;
  price_list_id: string;
  remote_id: string;
  remote_delete_error: string;
}> {
  return postJson<{
    deleted: boolean;
    deleted_remote: boolean;
    deleted_file: boolean;
    price_list_id: string;
    remote_id: string;
    remote_delete_error: string;
  }, Record<string, never>>(
    `/backoffice/suppliers/${code}/price-lists/${priceListId}/delete/`,
    {},
    undefined,
    { token },
  );
}

export async function importBackofficeSupplierPriceListToRaw(
  token: string,
  code: string,
  priceListId: string,
): Promise<BackofficeActionResponse & { price_list: BackofficeSupplierPriceList }> {
  return postJson<BackofficeActionResponse & { price_list: BackofficeSupplierPriceList }, Record<string, never>>(
    `/backoffice/suppliers/${code}/price-lists/${priceListId}/import/`,
    {},
    undefined,
    { token },
  );
}

export async function getBackofficeSupplierRuns(token: string, code: string, params?: BackofficeListQuery) {
  const data = await getJson<BackofficeImportRun[] | { results: BackofficeImportRun[]; count: number }>(
    `/backoffice/suppliers/${code}/runs/`,
    params,
    { token },
  );
  return normalizePaginatedListResponse(data);
}

export async function getBackofficeSupplierErrors(token: string, code: string, params?: BackofficeListQuery) {
  const data = await getJson<BackofficeImportError[] | { results: BackofficeImportError[]; count: number }>(
    `/backoffice/suppliers/${code}/errors/`,
    params,
    { token },
  );
  return normalizePaginatedListResponse(data);
}

export async function getBackofficeSupplierCooldown(token: string, code: string): Promise<BackofficeSupplierWorkspace["cooldown"] & { supplier_code: string }> {
  return getJson<BackofficeSupplierWorkspace["cooldown"] & { supplier_code: string }>(
    `/backoffice/suppliers/${code}/cooldown/`,
    undefined,
    { token },
  );
}
