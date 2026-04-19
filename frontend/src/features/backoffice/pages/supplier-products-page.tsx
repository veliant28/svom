"use client";

import { SupplierProductsFilters } from "@/features/backoffice/components/supplier-products/supplier-products-filters";
import { SupplierProductsTable } from "@/features/backoffice/components/supplier-products/supplier-products-table";
import { SupplierProductsToolbar } from "@/features/backoffice/components/supplier-products/supplier-products-toolbar";
import { SupplierCategoryMappingModal } from "@/features/backoffice/components/suppliers/supplier-category-mapping-modal";
import { useSupplierProductsPage } from "@/features/backoffice/hooks/use-supplier-products-page";

export function SupplierProductsPage() {
  const {
    t,
    tCommon,
    tUtr,
    tGpl,
    locale,
    scope,
    filters,
    token,
    rows,
    totalCount,
    pagesCount,
    isLoading,
    error,
    refetch,
    refreshAll,
    isCategoryMappingOpen,
    selectedRawOfferId,
    openCategoryMapping,
    closeCategoryMapping,
    isPublishing,
    publishDisabled,
    publishMapped,
    handleSupplierCodeChange,
  } = useSupplierProductsPage();

  return (
    <section>
      <SupplierProductsToolbar
        activeCode={scope.activeCode}
        onSupplierCodeChange={handleSupplierCodeChange}
        hrefFor={scope.hrefFor}
        onRefresh={() => {
          void refreshAll();
        }}
        t={t}
        tUtr={tUtr}
        tGpl={tGpl}
      />

      <SupplierProductsFilters
        t={t}
        tCommon={tCommon}
        q={filters.q}
        pageSize={filters.pageSize}
        pageSizeOptions={filters.pageSizeOptions}
        isPublishing={isPublishing}
        publishDisabled={publishDisabled}
        onSearchChange={filters.onSearchChange}
        onPageSizeChange={filters.onPageSizeChange}
        onPublishMapped={() => {
          void publishMapped();
        }}
      />

      <SupplierProductsTable
        t={t}
        tUtr={tUtr}
        tGpl={tGpl}
        rows={rows}
        isLoading={isLoading}
        error={error}
        totalCount={totalCount}
        page={filters.page}
        pagesCount={pagesCount}
        isCategoryMappingOpen={isCategoryMappingOpen}
        selectedRawOfferId={selectedRawOfferId}
        onOpenCategoryMapping={openCategoryMapping}
        onPageChange={filters.setPage}
      />

      <SupplierCategoryMappingModal
        isOpen={isCategoryMappingOpen}
        rawOfferId={selectedRawOfferId}
        token={token}
        locale={locale}
        onClose={closeCategoryMapping}
        onSaved={refetch}
      />
    </section>
  );
}
