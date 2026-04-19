"use client";

import { ProductsFilters } from "@/features/backoffice/components/products/products-filters";
import { ProductDeleteModal } from "@/features/backoffice/components/products/product-delete-modal";
import { ProductEditModal } from "@/features/backoffice/components/products/product-edit-modal";
import { ProductStatusModal } from "@/features/backoffice/components/products/product-status-modal";
import { ProductBulkCategoryModal } from "@/features/backoffice/components/products/product-bulk-category-modal";
import { ProductsTable } from "@/features/backoffice/components/products/products-table";
import { ProductsToolbar } from "@/features/backoffice/components/products/products-toolbar";
import { useProductsPage } from "@/features/backoffice/hooks/use-products-page";

export function ProductsPage() {
  const {
    t,
    tUtr,
    tGpl,
    locale,
    filters,
    rows,
    brands,
    categories,
    totalCount,
    pagesCount,
    isLoading,
    error,
    editingProduct,
    createOpen,
    editOpen,
    isSubmitting,
    deletingId,
    deleteTarget,
    form,
    bulkActions,
    openCreate,
    openEdit,
    closeCreate,
    closeEdit,
    requestDelete,
    setDeleteTarget,
    setFormPart,
    handleCreate,
    handleUpdate,
    handleDelete,
    refreshAll,
  } = useProductsPage();

  return (
    <section>
      <ProductsToolbar t={t} onRefresh={refreshAll} />

      <ProductsFilters
        t={t}
        q={filters.q}
        pageSize={filters.pageSize}
        pageSizeOptions={filters.pageSizeOptions}
        isActiveFilter={filters.isActiveFilter}
        brandFilter={filters.brandFilter}
        categoryFilter={filters.categoryFilter}
        brands={brands}
        categories={categories}
        onSearchChange={filters.onSearchChange}
        onPageSizeChange={filters.onPageSizeChange}
        onIsActiveFilterChange={filters.onIsActiveFilterChange}
        onBrandFilterChange={filters.onBrandFilterChange}
        onCategoryFilterChange={filters.onCategoryFilterChange}
        onCreate={openCreate}
        bulkActionsRef={bulkActions.bulkActionsRef}
        bulkActionsOpen={bulkActions.bulkActionsOpen}
        selectedCount={bulkActions.selectedSet.size}
        runningAction={bulkActions.runningAction}
        onToggleBulkActions={() => {
          bulkActions.setBulkActionsOpen((prev) => !prev);
        }}
        onBulkMoveCategory={() => {
          bulkActions.setBulkActionsOpen(false);
          bulkActions.setBulkMoveCategoryOpen(true);
        }}
        onBulkReindex={() => {
          bulkActions.setBulkActionsOpen(false);
          void bulkActions.runBulkReindex();
        }}
        onBulkDelete={() => {
          bulkActions.setBulkActionsOpen(false);
          bulkActions.setBulkDeleteOpen(true);
        }}
      />

      <ProductsTable
        t={t}
        tUtr={tUtr}
        tGpl={tGpl}
        locale={locale}
        rows={rows}
        isLoading={isLoading}
        error={error}
        selectedSet={bulkActions.selectedSet}
        allPageSelected={bulkActions.allPageSelected}
        somePageSelected={bulkActions.somePageSelected}
        deletingId={deletingId}
        page={filters.page}
        pagesCount={pagesCount}
        totalCount={totalCount}
        onToggleSelectAllPage={bulkActions.toggleSelectAllPage}
        onToggleSelected={bulkActions.toggleSelected}
        onOpenEdit={openEdit}
        onRequestDelete={requestDelete}
        onPageChange={filters.setPage}
      />

      <ProductEditModal
        mode="create"
        isOpen={createOpen}
        isSubmitting={isSubmitting}
        form={form}
        brands={brands}
        categories={categories}
        onClose={closeCreate}
        onSubmit={() => {
          void handleCreate();
        }}
        onChange={setFormPart}
        t={t}
      />

      <ProductEditModal
        mode="edit"
        isOpen={editOpen}
        isSubmitting={isSubmitting}
        form={form}
        brands={brands}
        categories={categories}
        onClose={closeEdit}
        onSubmit={() => {
          void handleUpdate();
        }}
        onChange={setFormPart}
        t={t}
      />

      <ProductDeleteModal
        isOpen={Boolean(deleteTarget)}
        isSubmitting={Boolean(deletingId)}
        productName={deleteTarget?.name ?? ""}
        onClose={() => {
          if (!deletingId) {
            setDeleteTarget(null);
          }
        }}
        onConfirm={() => {
          void handleDelete();
        }}
        t={t}
      />

      <ProductStatusModal
        isOpen={bulkActions.bulkDeleteOpen}
        isSubmitting={bulkActions.runningAction === "delete"}
        count={bulkActions.selectedSet.size}
        onClose={() => {
          if (bulkActions.runningAction !== "delete") {
            bulkActions.setBulkDeleteOpen(false);
          }
        }}
        onConfirm={() => {
          void bulkActions.runBulkDelete();
        }}
        t={t}
      />

      <ProductBulkCategoryModal
        isOpen={bulkActions.bulkMoveCategoryOpen}
        isSubmitting={bulkActions.runningAction === "move_category"}
        count={bulkActions.selectedSet.size}
        categories={categories}
        selectedCategoryId={bulkActions.bulkTargetCategoryId}
        onCategoryChange={bulkActions.setBulkTargetCategoryId}
        onClose={() => {
          if (bulkActions.runningAction !== "move_category") {
            bulkActions.setBulkMoveCategoryOpen(false);
          }
        }}
        onConfirm={() => {
          void bulkActions.runBulkMoveCategory();
        }}
        t={t}
      />

      {editOpen && !editingProduct ? (
        <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>{t("products.states.editingUnavailable")}</p>
      ) : null}
    </section>
  );
}
