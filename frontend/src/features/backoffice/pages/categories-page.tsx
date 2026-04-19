"use client";

import { CategoriesTable } from "@/features/backoffice/components/categories/categories-table";
import { CategoriesToolbar } from "@/features/backoffice/components/categories/categories-toolbar";
import { CategoryDeleteModal } from "@/features/backoffice/components/categories/category-delete-modal";
import { CategoryFormModal } from "@/features/backoffice/components/categories/category-form-modal";
import { useCategoriesPage } from "@/features/backoffice/hooks/use-categories-page";

export function CategoriesPage() {
  const {
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
    data,
    isLoading,
    error,
    rows,
    sortedParentOptions,
    pagesCount,
    getDisplayName,
    getDisplayParentName,
    getParentOptionLabel,
    editingCategory,
    disabledParentIds,
    form,
    actions,
  } = useCategoriesPage();

  return (
    <section>
      <CategoriesToolbar
        t={t}
        query={query}
        isActiveFilter={isActiveFilter}
        parentFilter={parentFilter}
        sortedParentOptions={sortedParentOptions}
        getParentOptionLabel={getParentOptionLabel}
        onQueryChange={(value) => {
          setQuery(value);
          setPage(1);
        }}
        onIsActiveFilterChange={(value) => {
          setIsActiveFilter(value);
          setPage(1);
        }}
        onParentFilterChange={(value) => {
          setParentFilter(value);
          setPage(1);
        }}
        onOpenCreate={form.openCreate}
      />

      <CategoriesTable
        t={t}
        locale={locale}
        rows={rows}
        isLoading={isLoading}
        error={error}
        totalCount={data?.count ?? 0}
        page={page}
        pagesCount={pagesCount}
        deletingCategoryId={actions.deletingCategoryId}
        getDisplayName={getDisplayName}
        getDisplayParentName={getDisplayParentName}
        onEdit={form.openEdit}
        onDelete={actions.requestDelete}
        onPageChange={setPage}
      />

      <CategoryFormModal
        title={t("categories.create.title")}
        submitLabel={t("categories.actions.create")}
        isOpen={form.createModalOpen}
        isSubmitting={actions.isCreating}
        name={form.createName}
        parentId={form.createParentId}
        isActive={form.createIsActive}
        parentOptions={sortedParentOptions}
        getParentOptionLabel={getParentOptionLabel}
        onNameChange={form.setCreateName}
        onParentChange={form.setCreateParentId}
        onIsActiveChange={form.setCreateIsActive}
        onClose={() => {
          if (actions.isCreating) {
            return;
          }
          form.closeCreate();
        }}
        onSubmit={() => {
          void actions.createCategory();
        }}
        t={t}
      />

      <CategoryFormModal
        title={editingCategory ? t("categories.edit.title", { name: getDisplayName(editingCategory, locale) }) : t("categories.edit.fallbackTitle")}
        submitLabel={t("categories.actions.save")}
        isOpen={form.editModalOpen}
        isSubmitting={actions.isUpdating}
        name={form.editName}
        parentId={form.editParentId}
        isActive={form.editIsActive}
        parentOptions={sortedParentOptions}
        disabledParentIds={disabledParentIds}
        getParentOptionLabel={getParentOptionLabel}
        onNameChange={form.setEditName}
        onParentChange={form.setEditParentId}
        onIsActiveChange={form.setEditIsActive}
        onClose={() => {
          if (actions.isUpdating) {
            return;
          }
          form.closeEdit();
        }}
        onSubmit={() => {
          void actions.updateCategory();
        }}
        t={t}
      />

      <CategoryDeleteModal
        isOpen={Boolean(actions.deleteTarget)}
        message={actions.deleteTarget ? t("categories.messages.deleteConfirm", { name: getDisplayName(actions.deleteTarget, locale) }) : ""}
        onClose={actions.closeDelete}
        onConfirm={() => {
          void actions.confirmDelete();
        }}
      />
    </section>
  );
}
