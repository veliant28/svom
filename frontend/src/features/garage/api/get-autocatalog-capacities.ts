import { getJson } from "@/shared/api/http-client";
import { normalizeListResponse, type ListResponse } from "@/shared/api/normalize-list-response";

import type { AutocatalogCapacityOption } from "@/features/garage/types/garage";

export async function getAutocatalogCapacities(
  makeId: number,
  modelId: number,
  modification: string,
  year?: number,
): Promise<AutocatalogCapacityOption[]> {
  const data = await getJson<ListResponse<AutocatalogCapacityOption>>("/autocatalog/garage/capacities/", {
    make: makeId,
    model: modelId,
    modification,
    year,
  });
  return normalizeListResponse(data);
}
