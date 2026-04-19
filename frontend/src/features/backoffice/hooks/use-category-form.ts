import { useCallback, useState } from "react";

import type { BackofficeCatalogCategory } from "@/features/backoffice/types/catalog.types";

export function useCategoryForm() {
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createParentId, setCreateParentId] = useState("");
  const [createIsActive, setCreateIsActive] = useState(true);

  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingCategoryId, setEditingCategoryId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editParentId, setEditParentId] = useState("");
  const [editIsActive, setEditIsActive] = useState(true);

  const resetCreate = useCallback(() => {
    setCreateName("");
    setCreateParentId("");
    setCreateIsActive(true);
  }, []);

  const resetEdit = useCallback(() => {
    setEditingCategoryId(null);
    setEditName("");
    setEditParentId("");
    setEditIsActive(true);
  }, []);

  const openCreate = useCallback(() => {
    setCreateModalOpen(true);
  }, []);

  const closeCreate = useCallback(() => {
    setCreateModalOpen(false);
    resetCreate();
  }, [resetCreate]);

  const openEdit = useCallback((category: BackofficeCatalogCategory) => {
    setEditingCategoryId(category.id);
    setEditName(category.name);
    setEditParentId(category.parent ?? "");
    setEditIsActive(category.is_active);
    setEditModalOpen(true);
  }, []);

  const closeEdit = useCallback(() => {
    setEditModalOpen(false);
    resetEdit();
  }, [resetEdit]);

  return {
    createModalOpen,
    createName,
    setCreateName,
    createParentId,
    setCreateParentId,
    createIsActive,
    setCreateIsActive,
    editModalOpen,
    editingCategoryId,
    editName,
    setEditName,
    editParentId,
    setEditParentId,
    editIsActive,
    setEditIsActive,
    openCreate,
    closeCreate,
    openEdit,
    closeEdit,
    resetCreate,
    resetEdit,
  };
}
