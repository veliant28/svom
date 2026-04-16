import { getJson } from "@/shared/api/http-client";
import { normalizeListResponse, type ListResponse } from "@/shared/api/normalize-list-response";

import type { AutocatalogMakeOption } from "@/features/garage/types/garage";

export async function getAutocatalogMakes(year?: number): Promise<AutocatalogMakeOption[]> {
  const data = await getJson<ListResponse<AutocatalogMakeOption>>("/autocatalog/garage/makes/", { year });
  return normalizeListResponse(data);
}
