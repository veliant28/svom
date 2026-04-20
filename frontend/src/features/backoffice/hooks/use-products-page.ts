import { useCallback, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useProductsActions } from "@/features/backoffice/hooks/products/use-products-actions";
import { useProductsBulkActions } from "@/features/backoffice/hooks/products/use-products-bulk-actions";
import { useProductsDerivedState } from "@/features/backoffice/hooks/products/use-products-derived-state";
import { useProductsFilters } from "@/features/backoffice/hooks/products/use-products-filters";
import { useProductsPageData } from "@/features/backoffice/hooks/products/use-products-page-data";

export function useProductsPage() {
  const t = useTranslations("backoffice.common");
  const tUtr = useTranslations("backoffice.utr");
  const tGpl = useTranslations("backoffice.gpl");
  const locale = useLocale();
  const { showApiError, showSuccess } = useBackofficeFeedback();

  const filters = useProductsFilters();
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  const removeSelectedIds = useCallback((deletedIds: string[]) => {
    setSelectedIds((prev) => prev.filter((id) => !deletedIds.includes(id)));
  }, []);

  const data = useProductsPageData(filters, locale);

  const actions = useProductsActions({
    token: data.token,
    refetch: data.refetch,
    feedback: { showSuccess, showApiError },
    onAfterDelete: removeSelectedIds,
  });

  const handleAfterBulkDelete = useCallback((deletedIds: string[]) => {
    removeSelectedIds(deletedIds);
    actions.handleDeletedProducts(deletedIds);
  }, [actions, removeSelectedIds]);

  const bulkActions = useProductsBulkActions({
    token: data.token,
    rows: data.rows,
    selectedIds,
    setSelectedIds,
    feedback: { showSuccess, showApiError },
    onAfterDelete: handleAfterBulkDelete,
    refetch: data.refetch,
  });

  const derived = useProductsDerivedState({
    locale,
    rawCategories: data.rawCategories,
    rows: data.rows,
    editingId: actions.editingId,
    productsCount: data.productsCount,
    pageSize: filters.pageSize,
    refetch: data.refetch,
    refetchBrands: data.refetchBrands,
    refetchCategories: data.refetchCategories,
  });

  return {
    t,
    tUtr,
    tGpl,
    locale,
    filters,
    rows: data.rows,
    brands: data.brands,
    categories: derived.categories,
    totalCount: derived.totalCount,
    pagesCount: derived.pagesCount,
    isLoading: data.isLoading,
    error: data.error,
    editingProduct: derived.editingProduct,
    createOpen: actions.createOpen,
    editOpen: actions.editOpen,
    isSubmitting: actions.isSubmitting,
    deletingId: actions.deletingId,
    deleteTarget: actions.deleteTarget,
    form: actions.form,
    bulkActions,
    openCreate: actions.openCreate,
    openEdit: actions.openEdit,
    closeCreate: actions.closeCreate,
    closeEdit: actions.closeEdit,
    requestDelete: actions.requestDelete,
    setDeleteTarget: actions.setDeleteTarget,
    setFormPart: actions.setFormPart,
    handleCreate: actions.handleCreate,
    handleUpdate: actions.handleUpdate,
    handleDelete: actions.handleDelete,
    refreshAll: derived.refreshAll,
  };
}
