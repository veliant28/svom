"use client";

import { usePathname, useSearchParams } from "next/navigation";

export function buildCatalogCategoryHref(categoryId: string): string {
  return `/catalog?category_id=${encodeURIComponent(categoryId)}`;
}

export function useActiveCatalogCategoryKey(): string | null {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  if (!/(^|\/)catalog(\/|$)/.test(pathname)) {
    return null;
  }

  const categoryId = searchParams.get("category_id");
  if (categoryId && categoryId.trim().length > 0) {
    return categoryId;
  }

  const categorySlug = searchParams.get("category");
  return categorySlug && categorySlug.trim().length > 0 ? categorySlug : null;
}
