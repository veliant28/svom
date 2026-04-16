import { getJson } from "@/shared/api/http-client";
import { normalizeListResponse, type ListResponse } from "@/shared/api/normalize-list-response";

import type { AutocatalogEngineOption } from "@/features/garage/types/garage";

export async function getAutocatalogEngines(
  makeId: number,
  modelId: number,
  modification: string,
  capacity: string,
  year?: number,
): Promise<AutocatalogEngineOption[]> {
  const data = await getJson<ListResponse<AutocatalogEngineOption>>("/autocatalog/garage/engines/", {
    make: makeId,
    model: modelId,
    modification,
    capacity,
    year,
  });
  return normalizeListResponse(data);
}
