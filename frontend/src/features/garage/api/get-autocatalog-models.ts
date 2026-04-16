import { getJson } from "@/shared/api/http-client";
import { normalizeListResponse, type ListResponse } from "@/shared/api/normalize-list-response";

import type { AutocatalogModelOption } from "@/features/garage/types/garage";

export async function getAutocatalogModels(makeId: number, year?: number): Promise<AutocatalogModelOption[]> {
  const data = await getJson<ListResponse<AutocatalogModelOption>>("/autocatalog/garage/models/", {
    make: makeId,
    year,
  });
  return normalizeListResponse(data);
}
