import { deleteJson, getJson, patchJson, postJson } from "@/shared/api/http-client";
import { normalizePaginatedListResponse } from "@/shared/api/normalize-list-response";

import type {
  BackofficeActionResponse,
  BackofficeAutocatalogCar,
  BackofficeAutocatalogFilterOptions,
  BackofficeCatalogBrand,
  BackofficeCatalogCategory,
  BackofficeCatalogProduct,
  BackofficeCategoryMappingCategoryOption,
  BackofficeImportError,
  BackofficeImportQuality,
  BackofficeImportQualityComparison,
  BackofficeImportQualitySummary,
  BackofficeImportRun,
  BackofficeImportSource,
  BackofficeMatchingCandidateProduct,
  BackofficeMatchingSummary,
  BackofficeOrderOperational,
  BackofficePricingCategoryImpact,
  BackofficePricingControlPanel,
  BackofficeProcurementRecommendation,
  BackofficeRawOffer,
  BackofficeRawOfferCategoryMappingDetail,
  BackofficeSummary,
  BackofficeSupplierListItem,
  BackofficeSupplierOffer,
  BackofficeSupplierPublishMappedResult,
  BackofficeSupplierPriceList,
  BackofficeSupplierPriceListParams,
  BackofficeSupplierWorkspace,
  BackofficeUtrBrandImportSummary,
} from "@/features/backoffice/types/backoffice";

export type BackofficeListQuery = Record<string, string | number | boolean | undefined>;

export async function getBackofficeSummary(token: string): Promise<BackofficeSummary> {
  return getJson<BackofficeSummary>("/backoffice/summary/", undefined, { token });
}

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

export async function getBackofficeAutocatalog(token: string, params?: BackofficeListQuery) {
  const data = await getJson<BackofficeAutocatalogCar[] | { results: BackofficeAutocatalogCar[]; count: number }>(
    "/backoffice/autocatalog/",
    params,
    { token },
  );
  return normalizePaginatedListResponse(data);
}

export async function getBackofficeAutocatalogFilterOptions(
  token: string,
  params?: BackofficeListQuery,
): Promise<BackofficeAutocatalogFilterOptions> {
  return getJson<BackofficeAutocatalogFilterOptions>("/backoffice/autocatalog/filter-options/", params, { token });
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

export async function getBackofficePricingControlPanel(token: string): Promise<BackofficePricingControlPanel> {
  return getJson<BackofficePricingControlPanel>("/backoffice/pricing/control-panel/", undefined, { token });
}

export async function getBackofficePricingCategoryImpact(
  token: string,
  params: { category_id: string; include_children?: boolean },
): Promise<BackofficePricingCategoryImpact> {
  return getJson<BackofficePricingCategoryImpact>("/backoffice/pricing/category-impact/", params, { token });
}

export async function updateBackofficePricingGlobalMarkup(
  token: string,
  payload: { percent_markup: number; dispatch_async?: boolean },
): Promise<{
  mode: "sync" | "async";
  affected_products: number;
  created_policies: number;
  updated_policies: number;
  markup_percent: string;
}> {
  return postJson<
  {
    mode: "sync" | "async";
    affected_products: number;
    created_policies: number;
    updated_policies: number;
    markup_percent: string;
  },
  typeof payload
  >("/backoffice/pricing/global-markup/", payload, undefined, { token });
}

export async function updateBackofficePricingCategoryMarkup(
  token: string,
  payload: { category_id: string; percent_markup: number; include_children?: boolean; dispatch_async?: boolean },
): Promise<{
  mode: "sync" | "async";
  affected_products: number;
  target_categories: number;
  created_policies: number;
  updated_policies: number;
  markup_percent: string;
}> {
  return postJson<
  {
    mode: "sync" | "async";
    affected_products: number;
    target_categories: number;
    created_policies: number;
    updated_policies: number;
    markup_percent: string;
  },
  typeof payload
  >("/backoffice/pricing/category-markup/", payload, undefined, { token });
}

export async function runBackofficePricingRecalculate(
  token: string,
  payload: { dispatch_async?: boolean; category_id?: string; include_children?: boolean },
): Promise<{ mode: "sync" | "async"; affected_products: number; target_categories: number }> {
  return postJson<{ mode: "sync" | "async"; affected_products: number; target_categories: number }, typeof payload>(
    "/backoffice/pricing/recalculate/",
    payload,
    undefined,
    { token },
  );
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

export async function getBackofficeOrders(token: string, params?: BackofficeListQuery) {
  const data = await getJson<BackofficeOrderOperational[] | { results: BackofficeOrderOperational[]; count: number }>(
    "/backoffice/orders/",
    params,
    { token },
  );
  return normalizePaginatedListResponse(data);
}

export async function getBackofficeOrderDetail(token: string, orderId: string): Promise<BackofficeOrderOperational> {
  return getJson<BackofficeOrderOperational>(`/backoffice/orders/${orderId}/`, undefined, { token });
}

export async function confirmBackofficeOrder(
  token: string,
  payload: { order_id: string; operator_note?: string },
): Promise<{ order_id: string; status: string }> {
  return postJson<{ order_id: string; status: string }, typeof payload>("/backoffice/orders/actions/confirm/", payload, undefined, { token });
}

export async function markBackofficeOrderAwaitingProcurement(
  token: string,
  payload: { order_id: string; operator_note?: string },
): Promise<{ order_id: string; status: string }> {
  return postJson<{ order_id: string; status: string }, typeof payload>(
    "/backoffice/orders/actions/awaiting-procurement/",
    payload,
    undefined,
    { token },
  );
}

export async function reserveBackofficeOrder(
  token: string,
  payload: { order_id: string; item_ids?: string[]; operator_note?: string },
): Promise<{ order_id: string; status: string }> {
  return postJson<{ order_id: string; status: string }, typeof payload>("/backoffice/orders/actions/reserve/", payload, undefined, { token });
}

export async function markBackofficeOrderReadyToShip(
  token: string,
  payload: { order_id: string; operator_note?: string },
): Promise<{ order_id: string; status: string }> {
  return postJson<{ order_id: string; status: string }, typeof payload>("/backoffice/orders/actions/ready-to-ship/", payload, undefined, { token });
}

export async function cancelBackofficeOrder(
  token: string,
  payload: { order_id: string; reason_code: string; reason_note?: string; operator_note?: string },
): Promise<{ order_id: string; status: string }> {
  return postJson<{ order_id: string; status: string }, typeof payload>("/backoffice/orders/actions/cancel/", payload, undefined, { token });
}

export async function bulkConfirmBackofficeOrders(
  token: string,
  payload: { order_ids: string[]; operator_note?: string },
): Promise<{ updated: number }> {
  return postJson<{ updated: number }, typeof payload>("/backoffice/orders/actions/bulk-confirm/", payload, undefined, { token });
}

export async function bulkMarkAwaitingProcurementBackofficeOrders(
  token: string,
  payload: { order_ids: string[]; operator_note?: string },
): Promise<{ updated: number }> {
  return postJson<{ updated: number }, typeof payload>(
    "/backoffice/orders/actions/bulk-awaiting-procurement/",
    payload,
    undefined,
    { token },
  );
}

export async function getBackofficeOrderItemSupplierRecommendation(token: string, itemId: string): Promise<BackofficeProcurementRecommendation> {
  return getJson<BackofficeProcurementRecommendation>(`/backoffice/orders/items/${itemId}/supplier-recommendation/`, undefined, { token });
}

export async function overrideBackofficeOrderItemSupplier(
  token: string,
  itemId: string,
  payload: { supplier_offer_id: string; operator_note?: string },
): Promise<BackofficeProcurementRecommendation> {
  return postJson<BackofficeProcurementRecommendation, typeof payload>(
    `/backoffice/orders/items/${itemId}/supplier-override/`,
    payload,
    undefined,
    { token },
  );
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

export async function getBackofficeMatchingSummary(token: string): Promise<BackofficeMatchingSummary> {
  return getJson<BackofficeMatchingSummary>("/backoffice/matching/summary/", undefined, { token });
}

export async function getBackofficeUnmatchedOffers(token: string, params?: BackofficeListQuery) {
  const data = await getJson<BackofficeRawOffer[] | { results: BackofficeRawOffer[]; count: number }>(
    "/backoffice/matching/unmatched/",
    params,
    { token },
  );
  return normalizePaginatedListResponse(data);
}

export async function getBackofficeConflictOffers(token: string, params?: BackofficeListQuery) {
  const data = await getJson<BackofficeRawOffer[] | { results: BackofficeRawOffer[]; count: number }>(
    "/backoffice/matching/conflicts/",
    params,
    { token },
  );
  return normalizePaginatedListResponse(data);
}

export async function getBackofficeMatchingReview(token: string, reviewId: string): Promise<BackofficeRawOffer> {
  return getJson<BackofficeRawOffer>(`/backoffice/matching/review/${reviewId}/`, undefined, { token });
}

export async function getBackofficeMatchingCandidates(token: string, reviewId: string) {
  return getJson<{ count: number; results: BackofficeMatchingCandidateProduct[] }>(
    `/backoffice/matching/review/${reviewId}/candidates/`,
    undefined,
    { token },
  );
}

export async function confirmBackofficeMatch(
  token: string,
  payload: { raw_offer_id: string; product_id: string; note?: string },
): Promise<Record<string, unknown>> {
  return postJson<Record<string, unknown>, typeof payload>("/backoffice/matching/actions/confirm/", payload, undefined, { token });
}

export async function ignoreBackofficeOffer(
  token: string,
  payload: { raw_offer_id: string; note?: string },
): Promise<Record<string, unknown>> {
  return postJson<Record<string, unknown>, typeof payload>("/backoffice/matching/actions/ignore/", payload, undefined, { token });
}

export async function retryBackofficeMatching(
  token: string,
  payload: { raw_offer_id: string; note?: string },
): Promise<Record<string, unknown>> {
  return postJson<Record<string, unknown>, typeof payload>("/backoffice/matching/actions/retry/", payload, undefined, { token });
}

export async function bulkAutoMatchBackoffice(
  token: string,
  payload: { raw_offer_ids: string[]; note?: string },
): Promise<Record<string, unknown>> {
  return postJson<Record<string, unknown>, typeof payload>("/backoffice/matching/actions/bulk-auto-match/", payload, undefined, { token });
}

export async function bulkIgnoreBackoffice(
  token: string,
  payload: { raw_offer_ids: string[]; note?: string },
): Promise<Record<string, unknown>> {
  return postJson<Record<string, unknown>, typeof payload>("/backoffice/matching/actions/bulk-ignore/", payload, undefined, { token });
}

export async function applyManualMatchesBackoffice(
  token: string,
  payload: { mappings: Array<{ raw_offer_id: string; product_id: string }>; note?: string },
): Promise<Record<string, unknown>> {
  return postJson<Record<string, unknown>, typeof payload>(
    "/backoffice/matching/actions/apply-manual-matches/",
    payload,
    undefined,
    { token },
  );
}
