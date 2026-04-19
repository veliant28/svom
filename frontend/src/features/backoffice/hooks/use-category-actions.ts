import { useCallback, useState } from "react";

import {
  createBackofficeCatalogCategory,
  deleteBackofficeCatalogCategory,
  updateBackofficeCatalogCategory,
} from "@/features/backoffice/api/catalog-api";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import type { BackofficeCatalogCategory } from "@/features/backoffice/types/catalog.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function useCategoryActions({
  token,
  t,
  refetch,
  form,
}: {
  token: string | null;
  t: Translator;
  refetch: () => Promise<unknown>;
  form: {
    createName: string;
    createParentId: string;
    createIsActive: boolean;
    closeCreate: () => void;
    editName: string;
    editParentId: string;
    editIsActive: boolean;
    editingCategoryId: string | null;
    closeEdit: () => void;
  };
}) {
  const { showApiError, showSuccess } = useBackofficeFeedback();

  const [isCreating, setIsCreating] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [deletingCategoryId, setDeletingCategoryId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<BackofficeCatalogCategory | null>(null);

  const createCategory = useCallback(async () => {
    if (!token || isCreating) {
      return;
    }
    if (!form.createName.trim()) {
      showApiError(new Error(t("categories.messages.nameRequired")), t("categories.messages.createFailed"));
      return;
    }

    setIsCreating(true);
    try {
      await createBackofficeCatalogCategory(token, {
        name: form.createName,
        parent: form.createParentId || null,
        is_active: form.createIsActive,
      });
      showSuccess(t("categories.messages.created"));
      form.closeCreate();
      await refetch();
    } catch (actionError: unknown) {
      showApiError(actionError, t("categories.messages.createFailed"));
    } finally {
      setIsCreating(false);
    }
  }, [form, isCreating, refetch, showApiError, showSuccess, t, token]);

  const updateCategory = useCallback(async () => {
    if (!token || !form.editingCategoryId || isUpdating) {
      return;
    }
    if (!form.editName.trim()) {
      showApiError(new Error(t("categories.messages.nameRequired")), t("categories.messages.updateFailed"));
      return;
    }

    setIsUpdating(true);
    try {
      await updateBackofficeCatalogCategory(token, form.editingCategoryId, {
        name: form.editName,
        parent: form.editParentId || null,
        is_active: form.editIsActive,
      });
      showSuccess(t("categories.messages.updated"));
      form.closeEdit();
      await refetch();
    } catch (actionError: unknown) {
      showApiError(actionError, t("categories.messages.updateFailed"));
    } finally {
      setIsUpdating(false);
    }
  }, [form, isUpdating, refetch, showApiError, showSuccess, t, token]);

  const requestDelete = useCallback((category: BackofficeCatalogCategory) => {
    setDeleteTarget(category);
  }, []);

  const closeDelete = useCallback(() => {
    if (deletingCategoryId) {
      return;
    }
    setDeleteTarget(null);
  }, [deletingCategoryId]);

  const confirmDelete = useCallback(async () => {
    if (!token || deletingCategoryId || !deleteTarget) {
      return;
    }

    setDeletingCategoryId(deleteTarget.id);
    try {
      await deleteBackofficeCatalogCategory(token, deleteTarget.id);
      showSuccess(t("categories.messages.deleted"));
      if (form.editingCategoryId === deleteTarget.id) {
        form.closeEdit();
      }
      setDeleteTarget(null);
      await refetch();
    } catch (actionError: unknown) {
      showApiError(actionError, t("categories.messages.deleteFailed"));
    } finally {
      setDeletingCategoryId(null);
    }
  }, [deleteTarget, deletingCategoryId, form, refetch, showApiError, showSuccess, t, token]);

  return {
    isCreating,
    isUpdating,
    deletingCategoryId,
    deleteTarget,
    createCategory,
    updateCategory,
    requestDelete,
    closeDelete,
    confirmDelete,
  };
}
