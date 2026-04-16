import { getJson } from "@/shared/api/http-client";
import { normalizeListResponse, type ListResponse } from "@/shared/api/normalize-list-response";

import type { AutocatalogModificationOption } from "@/features/garage/types/garage";

export async function getAutocatalogModifications(
  makeId: number,
  modelId: number,
  year?: number,
): Promise<AutocatalogModificationOption[]> {
  const data = await getJson<ListResponse<AutocatalogModificationOption>>("/autocatalog/garage/modifications/", {
    make: makeId,
    model: modelId,
    year,
  });
  return normalizeListResponse(data);
}
