import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";

import {
  createBackofficeCatalogProduct,
  deleteBackofficeCatalogProduct,
  updateBackofficeCatalogProduct,
} from "@/features/backoffice/api/catalog-api";
import {
  DEFAULT_PRODUCT_FORM_STATE,
  type ProductFormState,
} from "@/features/backoffice/lib/products/product-form.types";
import type { BackofficeCatalogProduct } from "@/features/backoffice/types/catalog.types";

type BackofficeFeedback = {
  showSuccess: (message: string) => void;
  showApiError: (error: unknown, fallbackMessage?: string) => string;
};

export function useProductsActions({
  token,
  refetch,
  feedback,
  onAfterDelete,
}: {
  token: string | null;
  refetch: () => Promise<unknown>;
  feedback: BackofficeFeedback;
  onAfterDelete?: (deletedIds: string[]) => void;
}) {
  const t = useTranslations("backoffice.common");

  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<ProductFormState>(DEFAULT_PRODUCT_FORM_STATE);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<BackofficeCatalogProduct | null>(null);

  const resetForm = useCallback(() => {
    setForm(DEFAULT_PRODUCT_FORM_STATE);
  }, []);

  const openCreate = useCallback(() => {
    resetForm();
    setCreateOpen(true);
  }, [resetForm]);

  const openEdit = useCallback((item: BackofficeCatalogProduct) => {
    setEditingId(item.id);
    setForm({
      sku: item.sku,
      article: item.article,
      name: item.name,
      brand: item.brand,
      category: item.category,
      is_active: item.is_active,
      is_featured: item.is_featured,
      is_new: item.is_new,
      is_bestseller: item.is_bestseller,
    });
    setEditOpen(true);
  }, []);

  const closeCreate = useCallback(() => {
    setCreateOpen(false);
    resetForm();
  }, [resetForm]);

  const closeEdit = useCallback(() => {
    setEditOpen(false);
    setEditingId(null);
    resetForm();
  }, [resetForm]);

  const requestDelete = useCallback((item: BackofficeCatalogProduct) => {
    setDeleteTarget(item);
  }, []);

  const setFormPart = useCallback((next: Partial<ProductFormState>) => {
    setForm((prev) => ({ ...prev, ...next }));
  }, []);

  const handleDeletedProducts = useCallback((deletedIds: string[]) => {
    if (editingId && deletedIds.includes(editingId)) {
      closeEdit();
    }
    if (deleteTarget && deletedIds.includes(deleteTarget.id)) {
      setDeleteTarget(null);
    }
  }, [closeEdit, deleteTarget, editingId]);

  const handleCreate = useCallback(async () => {
    if (!token || isSubmitting) {
      return;
    }
    if (!form.sku.trim() || !form.name.trim() || !form.brand || !form.category) {
      feedback.showApiError(new Error(t("products.messages.required")), t("products.messages.createFailed"));
      return;
    }

    setIsSubmitting(true);
    try {
      await createBackofficeCatalogProduct(token, form);
      feedback.showSuccess(t("products.messages.created"));
      closeCreate();
      await refetch();
    } catch (actionError: unknown) {
      feedback.showApiError(actionError, t("products.messages.createFailed"));
    } finally {
      setIsSubmitting(false);
    }
  }, [closeCreate, feedback, form, isSubmitting, refetch, t, token]);

  const handleUpdate = useCallback(async () => {
    if (!token || !editingId || isSubmitting) {
      return;
    }
    if (!form.sku.trim() || !form.name.trim() || !form.brand || !form.category) {
      feedback.showApiError(new Error(t("products.messages.required")), t("products.messages.updateFailed"));
      return;
    }

    setIsSubmitting(true);
    try {
      await updateBackofficeCatalogProduct(token, editingId, form);
      feedback.showSuccess(t("products.messages.updated"));
      closeEdit();
      await refetch();
    } catch (actionError: unknown) {
      feedback.showApiError(actionError, t("products.messages.updateFailed"));
    } finally {
      setIsSubmitting(false);
    }
  }, [closeEdit, editingId, feedback, form, isSubmitting, refetch, t, token]);

  const handleDelete = useCallback(async () => {
    if (!token || deletingId || !deleteTarget) {
      return;
    }

    const deletedId = deleteTarget.id;
    setDeletingId(deletedId);
    try {
      await deleteBackofficeCatalogProduct(token, deletedId);
      feedback.showSuccess(t("products.messages.deleted"));
      if (onAfterDelete) {
        onAfterDelete([deletedId]);
      }
      handleDeletedProducts([deletedId]);
      await refetch();
    } catch (actionError: unknown) {
      feedback.showApiError(actionError, t("products.messages.deleteFailed"));
    } finally {
      setDeletingId(null);
    }
  }, [deleteTarget, deletingId, feedback, handleDeletedProducts, onAfterDelete, refetch, t, token]);

  return {
    createOpen,
    editOpen,
    editingId,
    form,
    isSubmitting,
    deletingId,
    deleteTarget,
    openCreate,
    openEdit,
    closeCreate,
    closeEdit,
    requestDelete,
    setDeleteTarget,
    setFormPart,
    handleDeletedProducts,
    handleCreate,
    handleUpdate,
    handleDelete,
  };
}
