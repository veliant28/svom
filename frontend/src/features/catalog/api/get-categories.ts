import { getJson } from "@/shared/api/http-client";
import { normalizeListResponse, type ListResponse } from "@/shared/api/normalize-list-response";
import type { HeaderCategoryParent } from "@/shared/components/layout/header/categories/header-category.types";

import type { CategorySummary } from "../types";

export async function getCategories(locale?: string): Promise<CategorySummary[]> {
  const data = await getJson<ListResponse<CategorySummary>>(
    "/catalog/categories",
    locale ? { locale } : undefined,
  );
  return normalizeListResponse(data);
}

export async function getHeaderCategories(locale?: string): Promise<CategorySummary[]> {
  const data = await getJson<ListResponse<CategorySummary>>(
    "/catalog/categories",
    {
      ...(locale ? { locale } : {}),
      scope: "header",
    },
  );
  return normalizeListResponse(data);
}

export async function getHeaderNavigation(locale?: string): Promise<HeaderCategoryParent[]> {
  const data = await getJson<ListResponse<HeaderCategoryParent>>(
    "/catalog/navigation/header",
    locale ? { locale } : undefined,
  );
  return normalizeListResponse(data);
}
