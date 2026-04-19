import { useCallback, useMemo } from "react";

import type { CategoryOption } from "@/features/backoffice/lib/products/product-form.types";
import type { BackofficeCatalogCategory, BackofficeCatalogProduct } from "@/features/backoffice/types/catalog.types";

export function useProductsDerivedState({
  locale,
  rawCategories,
  rows,
  editingId,
  productsCount,
  pageSize,
  refetch,
  refetchBrands,
  refetchCategories,
}: {
  locale: string;
  rawCategories: BackofficeCatalogCategory[];
  rows: BackofficeCatalogProduct[];
  editingId: string | null;
  productsCount: number;
  pageSize: number;
  refetch: () => Promise<unknown>;
  refetchBrands: () => Promise<unknown>;
  refetchCategories: () => Promise<unknown>;
}) {
  const categoriesById = useMemo(
    () =>
      rawCategories.reduce<Record<string, BackofficeCatalogCategory>>((acc, item) => {
        acc[item.id] = item;
        return acc;
      }, {}),
    [rawCategories],
  );

  const getDisplayCategoryName = useCallback(
    (category: BackofficeCatalogCategory): string => {
      if (locale === "ru") {
        return category.name_ru || category.name_uk || category.name;
      }
      if (locale === "en") {
        return category.name_en || category.name_uk || category.name;
      }
      return category.name_uk || category.name;
    },
    [locale],
  );

  const buildCategoryLineage = useCallback(
    (category: BackofficeCatalogCategory): string[] => {
      const lineage: string[] = [];
      const visited = new Set<string>();
      let current: BackofficeCatalogCategory | null = category;

      while (current && !visited.has(current.id)) {
        visited.add(current.id);
        lineage.unshift(getDisplayCategoryName(current));
        if (!current.parent) {
          break;
        }
        const parentCategory: BackofficeCatalogCategory | undefined = categoriesById[current.parent];
        if (!parentCategory) {
          if (current.parent_name) {
            lineage.unshift(current.parent_name);
          }
          break;
        }
        current = parentCategory;
      }

      return lineage;
    },
    [categoriesById, getDisplayCategoryName],
  );

  const categories = useMemo<CategoryOption[]>(() => {
    const withKeys = rawCategories.map((item) => {
      const lineage = buildCategoryLineage(item);
      return {
        item,
        depth: Math.max(lineage.length - 1, 0),
        sortKey: (lineage.length ? lineage.join(" > ") : getDisplayCategoryName(item)).toLowerCase(),
      };
    });

    withKeys.sort((a, b) => a.sortKey.localeCompare(b.sortKey, locale));

    return withKeys.map(({ item, depth }) => {
      const treePrefix = depth > 0 ? `${"|    ".repeat(Math.max(0, depth - 1))}|---- ` : "";
      return {
        id: item.id,
        label: `${treePrefix}${getDisplayCategoryName(item)}`,
      };
    });
  }, [buildCategoryLineage, getDisplayCategoryName, locale, rawCategories]);

  const pagesCount = useMemo(() => Math.max(1, Math.ceil(productsCount / pageSize)), [pageSize, productsCount]);
  const totalCount = productsCount;

  const editingProduct = useMemo(() => rows.find((item) => item.id === editingId) ?? null, [editingId, rows]);

  const refreshAll = useCallback(() => {
    void Promise.all([refetch(), refetchBrands(), refetchCategories()]);
  }, [refetch, refetchBrands, refetchCategories]);

  return {
    categories,
    pagesCount,
    totalCount,
    editingProduct,
    refreshAll,
  };
}
