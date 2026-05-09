import { useCallback, useState } from "react";

import type { BackofficeCatalogCategory } from "@/features/backoffice/types/catalog.types";

export function useCategoryForm() {
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createParentId, setCreateParentId] = useState("");
  const [createIsActive, setCreateIsActive] = useState(true);
  const [createShowInHeader, setCreateShowInHeader] = useState(false);

  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingCategoryId, setEditingCategoryId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editParentId, setEditParentId] = useState("");
  const [editIsActive, setEditIsActive] = useState(true);
  const [editShowInHeader, setEditShowInHeader] = useState(false);

  const resetCreate = useCallback(() => {
    setCreateName("");
    setCreateParentId("");
    setCreateIsActive(true);
    setCreateShowInHeader(false);
  }, []);

  const resetEdit = useCallback(() => {
    setEditingCategoryId(null);
    setEditName("");
    setEditParentId("");
    setEditIsActive(true);
    setEditShowInHeader(false);
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
    setEditShowInHeader(category.show_in_header);
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
    createShowInHeader,
    setCreateShowInHeader,
    editModalOpen,
    editingCategoryId,
    editName,
    setEditName,
    editParentId,
    setEditParentId,
    editIsActive,
    setEditIsActive,
    editShowInHeader,
    setEditShowInHeader,
    openCreate,
    closeCreate,
    openEdit,
    closeEdit,
    resetCreate,
    resetEdit,
  };
}
