import { getJson } from "@/shared/api/http-client";
import { normalizePaginatedListResponse } from "@/shared/api/normalize-list-response";

import type { BackofficeAutocatalogCar, BackofficeAutocatalogFilterOptions } from "@/features/backoffice/types/backoffice";

import type { BackofficeListQuery } from "./backoffice-api.types";

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
