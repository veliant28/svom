import { getJson } from "@/shared/api/http-client";
import { normalizeListResponse, type ListResponse } from "@/shared/api/normalize-list-response";

import type { CategorySummary } from "../types";

export async function getCategories(locale?: string): Promise<CategorySummary[]> {
  const data = await getJson<ListResponse<CategorySummary>>(
    "/catalog/categories/",
    locale ? { locale } : undefined,
  );
  return normalizeListResponse(data);
}
