import { deleteJson, getJson, patchJson, postJson } from "@/shared/api/http-client";
import { normalizePaginatedListResponse } from "@/shared/api/normalize-list-response";

import type {
  BackofficeActionResponse,
  BackofficeCategoryMappingCategoryOption,
  BackofficeImportError,
  BackofficeImportQuality,
  BackofficeImportQualityComparison,
  BackofficeImportQualitySummary,
  BackofficeImportRun,
  BackofficeImportSource,
  BackofficeRawOffer,
  BackofficeRawOfferCategoryMappingDetail,
} from "@/features/backoffice/types/backoffice";

import type { BackofficeListQuery } from "./backoffice-api.types";

export async function getBackofficeImportSchedules(token: string, params?: BackofficeListQuery) {
  const data = await getJson<BackofficeImportSource[] | { results: BackofficeImportSource[]; count: number }>(
    "/backoffice/import-schedules/",
    params,
    { token },
  );
  return normalizePaginatedListResponse(data);
}

export async function updateBackofficeImportSchedule(
  token: string,
  sourceId: string,
  payload: Partial<{
    is_auto_import_enabled: boolean;
    schedule_cron: string;
    schedule_timezone: string;
    schedule_start_date: string | null;
    schedule_run_time: string;
    schedule_every_day: boolean;
    auto_reprice_after_import: boolean;
    auto_reindex_after_import: boolean;
    is_active: boolean;
  }>,
): Promise<BackofficeImportSource> {
  return patchJson<BackofficeImportSource, typeof payload>(`/backoffice/import-schedules/${sourceId}/`, payload, undefined, { token });
}

export async function getBackofficeImportRuns(token: string, params?: BackofficeListQuery) {
  const data = await getJson<BackofficeImportRun[] | { results: BackofficeImportRun[]; count: number }>(
    "/backoffice/import-runs/",
    params,
    { token },
  );
  return normalizePaginatedListResponse(data);
}

export async function getBackofficeImportErrors(token: string, params?: BackofficeListQuery) {
  const data = await getJson<BackofficeImportError[] | { results: BackofficeImportError[]; count: number }>(
    "/backoffice/import-errors/",
    params,
    { token },
  );
  return normalizePaginatedListResponse(data);
}

export async function getBackofficeRawOffers(token: string, params?: BackofficeListQuery) {
  const data = await getJson<BackofficeRawOffer[] | { results: BackofficeRawOffer[]; count: number }>(
    "/backoffice/raw-offers/",
    params,
    { token },
  );
  return normalizePaginatedListResponse(data);
}

export async function getBackofficeRawOfferCategoryMapping(
  token: string,
  rawOfferId: string,
  params?: BackofficeListQuery,
): Promise<BackofficeRawOfferCategoryMappingDetail> {
  return getJson<BackofficeRawOfferCategoryMappingDetail>(
    `/backoffice/raw-offers/${rawOfferId}/category-mapping/`,
    params,
    { token },
  );
}

export async function setBackofficeRawOfferCategoryMapping(
  token: string,
  rawOfferId: string,
  payload: { category_id: string },
): Promise<BackofficeRawOfferCategoryMappingDetail> {
  return patchJson<BackofficeRawOfferCategoryMappingDetail, typeof payload>(
    `/backoffice/raw-offers/${rawOfferId}/category-mapping/`,
    payload,
    undefined,
    { token },
  );
}

export async function clearBackofficeRawOfferCategoryMapping(
  token: string,
  rawOfferId: string,
): Promise<BackofficeRawOfferCategoryMappingDetail> {
  return deleteJson<BackofficeRawOfferCategoryMappingDetail>(
    `/backoffice/raw-offers/${rawOfferId}/category-mapping/`,
    undefined,
    { token },
  );
}

export async function searchBackofficeCategoryMappingCategories(token: string, params?: BackofficeListQuery) {
  const data = await getJson<BackofficeCategoryMappingCategoryOption[] | { results: BackofficeCategoryMappingCategoryOption[]; count: number }>(
    "/backoffice/raw-offers/category-mapping/categories/",
    params,
    { token },
  );
  return normalizePaginatedListResponse(data);
}

export async function getBackofficeImportQualitySummary(token: string): Promise<BackofficeImportQualitySummary> {
  return getJson<BackofficeImportQualitySummary>("/backoffice/import-quality/summary/", undefined, { token });
}

export async function getBackofficeImportQualityRuns(token: string, params?: BackofficeListQuery) {
  const data = await getJson<BackofficeImportQuality[] | { results: BackofficeImportQuality[]; count: number }>(
    "/backoffice/import-quality/runs/",
    params,
    { token },
  );
  return normalizePaginatedListResponse(data);
}

export async function getBackofficeImportQualityDetail(token: string, runId: string): Promise<BackofficeImportQuality> {
  return getJson<BackofficeImportQuality>(`/backoffice/import-quality/runs/${runId}/`, undefined, { token });
}

export async function getBackofficeImportQualityCompare(token: string, runId: string): Promise<BackofficeImportQualityComparison> {
  return getJson<BackofficeImportQualityComparison>(`/backoffice/import-quality/runs/${runId}/compare/`, undefined, { token });
}

export async function runImportSourceAction(
  token: string,
  payload: {
    source_code: string;
    dry_run: boolean;
    dispatch_async?: boolean;
  },
): Promise<BackofficeActionResponse> {
  return postJson<BackofficeActionResponse, typeof payload>("/backoffice/actions/run-source/", payload, undefined, { token });
}

export async function runImportAllAction(
  token: string,
  payload: {
    dry_run: boolean;
    dispatch_async?: boolean;
  },
): Promise<BackofficeActionResponse> {
  return postJson<BackofficeActionResponse, typeof payload>("/backoffice/actions/import-all/", payload, undefined, { token });
}

export async function runRepriceAfterImportAction(
  token: string,
  payload: {
    run_id: string;
    dispatch_async?: boolean;
  },
): Promise<BackofficeActionResponse> {
  return postJson<BackofficeActionResponse, typeof payload>("/backoffice/actions/reprice-after-import/", payload, undefined, { token });
}
