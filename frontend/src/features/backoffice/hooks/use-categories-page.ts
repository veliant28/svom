import { useCallback, useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { getBackofficeCatalogCategories } from "@/features/backoffice/api/catalog-api";
import { useBackofficeQuery } from "@/features/backoffice/hooks/use-backoffice-query";
import { useCategoryActions } from "@/features/backoffice/hooks/use-category-actions";
import { useCategoryForm } from "@/features/backoffice/hooks/use-category-form";
import { getCategoryDisplayName, getCategoryParentDisplayName } from "@/features/backoffice/lib/categories/category-formatters";
import {
  buildChildIdsByParentId,
  buildDisabledParentIds,
  getCategoryParentOptionLabel,
  sortCategoryParentOptions,
} from "@/features/backoffice/lib/categories/category-tree-utils";
import type { BackofficeCatalogCategory } from "@/features/backoffice/types/catalog.types";

export function useCategoriesPage() {
  const t = useTranslations("backoffice.common");
  const locale = useLocale();

  const [query, setQuery] = useState("");
  const [isActiveFilter, setIsActiveFilter] = useState("");
  const [parentFilter, setParentFilter] = useState("");
  const [page, setPage] = useState(1);

  const form = useCategoryForm();

  const queryFn = useCallback(
    (token: string) =>
      getBackofficeCatalogCategories(token, {
        locale,
        q: query,
        is_active: isActiveFilter,
        parent: parentFilter,
        page,
      }),
    [isActiveFilter, locale, page, parentFilter, query],
  );

  const { token, data, isLoading, error, refetch } = useBackofficeQuery<{ count: number; results: BackofficeCatalogCategory[] }>(queryFn, [
    query,
    isActiveFilter,
    parentFilter,
    page,
    locale,
  ]);

  const parentOptionsQueryFn = useCallback(
    (tokenValue: string) => getBackofficeCatalogCategories(tokenValue, { page_size: 500, locale }),
    [locale],
  );

  const { data: parentOptionsData } = useBackofficeQuery<{ count: number; results: BackofficeCatalogCategory[] }>(
    parentOptionsQueryFn,
    [],
  );

  const rows = data?.results ?? [];
  const parentOptions = parentOptionsData?.results ?? [];

  const parentById = useMemo(
    () =>
      parentOptions.reduce<Record<string, BackofficeCatalogCategory>>((acc, item) => {
        acc[item.id] = item;
        return acc;
      }, {}),
    [parentOptions],
  );

  const getDisplayName = useCallback(
    (category: BackofficeCatalogCategory, currentLocale = locale) => getCategoryDisplayName(category, currentLocale),
    [locale],
  );

  const getDisplayParentName = useCallback(
    (category: BackofficeCatalogCategory) => getCategoryParentDisplayName({ category, parentById, locale }),
    [locale, parentById],
  );

  const getParentOptionLabel = useCallback(
    (category: BackofficeCatalogCategory) => getCategoryParentOptionLabel({ category, parentById, locale }),
    [locale, parentById],
  );

  const sortedParentOptions = useMemo(
    () => sortCategoryParentOptions({ categories: parentOptions, parentById, locale }),
    [locale, parentById, parentOptions],
  );

  const pagesCount = useMemo(() => {
    const total = data?.count ?? 0;
    return Math.max(1, Math.ceil(total / 20));
  }, [data?.count]);

  const editingCategory = useMemo(
    () => rows.find((item) => item.id === form.editingCategoryId) ?? parentOptions.find((item) => item.id === form.editingCategoryId) ?? null,
    [form.editingCategoryId, parentOptions, rows],
  );

  const childIdsByParentId = useMemo(() => buildChildIdsByParentId(parentOptions), [parentOptions]);

  const disabledParentIds = useMemo(
    () => buildDisabledParentIds({ editingCategoryId: form.editingCategoryId, childIdsByParentId }),
    [childIdsByParentId, form.editingCategoryId],
  );

  const actions = useCategoryActions({
    token,
    t,
    refetch,
    form: {
      createName: form.createName,
      createParentId: form.createParentId,
      createIsActive: form.createIsActive,
      closeCreate: form.closeCreate,
      editName: form.editName,
      editParentId: form.editParentId,
      editIsActive: form.editIsActive,
      editingCategoryId: form.editingCategoryId,
      closeEdit: form.closeEdit,
    },
  });

  return {
    t,
    locale,
    query,
    setQuery,
    isActiveFilter,
    setIsActiveFilter,
    parentFilter,
    setParentFilter,
    page,
    setPage,
    token,
    data,
    isLoading,
    error,
    refetch,
    rows,
    parentOptions,
    sortedParentOptions,
    pagesCount,
    getDisplayName,
    getDisplayParentName,
    getParentOptionLabel,
    editingCategory,
    disabledParentIds,
    form,
    actions,
  };
}
