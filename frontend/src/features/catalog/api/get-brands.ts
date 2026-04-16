import { getJson } from "@/shared/api/http-client";
import { normalizeListResponse, type ListResponse } from "@/shared/api/normalize-list-response";

import type { BrandSummary } from "../types";

export async function getBrands(): Promise<BrandSummary[]> {
  const data = await getJson<ListResponse<BrandSummary>>("/catalog/brands/");
  return normalizeListResponse(data);
}
