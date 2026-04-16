import { getJson } from "@/shared/api/http-client";
import { normalizeListResponse, type ListResponse } from "@/shared/api/normalize-list-response";

import type { AutocatalogYearOption } from "@/features/garage/types/garage";

type GetAutocatalogYearsParams = {
  make?: number;
  model?: number;
  modification?: string;
  capacity?: string;
  engine?: number;
};

export async function getAutocatalogYears(params?: GetAutocatalogYearsParams): Promise<AutocatalogYearOption[]> {
  const data = await getJson<ListResponse<AutocatalogYearOption>>("/autocatalog/garage/years/", params);
  return normalizeListResponse(data);
}
