"use client";

import { SupplierImportActions } from "@/features/backoffice/components/supplier-import/supplier-import-actions";
import { SupplierImportFooter } from "@/features/backoffice/components/supplier-import/supplier-import-empty-state";
import { SupplierImportProgressPanel } from "@/features/backoffice/components/supplier-import/supplier-import-progress-panel";
import { SupplierImportRunsTable } from "@/features/backoffice/components/supplier-import/supplier-import-runs-table";
import { SupplierImportToolbar } from "@/features/backoffice/components/supplier-import/supplier-import-toolbar";
import { AsyncState } from "@/features/backoffice/components/widgets/async-state";
import { useSupplierImportPage } from "@/features/backoffice/hooks/use-supplier-import-page";

export function SupplierImportPage() {
  const {
    t,
    tUtr,
    tGpl,
    tErrors,
    scope,
    supplierParams,
    rows,
    priceListsLoading,
    priceListsError,
    refetchPriceLists,
    tokenReady,
    filters,
    actions,
    lifecycle,
    paramsSourceLabel,
    requestPrimary,
    downloadPrimary,
    importPrimary,
    cooldownCanRun,
    cooldownSecondsLeft,
    refreshAll,
  } = useSupplierImportPage();

  return (
    <section>
      <SupplierImportToolbar
        activeCode={scope.activeCode}
        setActiveCode={scope.setActiveCode}
        hrefFor={scope.hrefFor}
        onRefresh={() => {
          void refreshAll();
        }}
        t={t}
        tUtr={tUtr}
        tGpl={tGpl}
      />

      <AsyncState
        isLoading={scope.suppliersLoading || scope.workspaceLoading}
        error={scope.suppliersError || scope.workspaceError}
        empty={!scope.workspace}
        emptyLabel={t("states.emptyWorkspace")}
      >
        {scope.workspace ? (
          <div className="grid gap-4">
            <section className="grid gap-4 lg:grid-cols-2">
              <SupplierImportActions
                t={t}
                tokenReady={tokenReady}
                cooldownCanRun={cooldownCanRun}
                supplierParams={supplierParams}
                format={filters.format}
                formatOptions={filters.formatOptions}
                inStockOnly={filters.inStockOnly}
                showScancode={filters.showScancode}
                utrArticle={filters.utrArticle}
                onFormatChange={filters.setFormat}
                onInStockOnlyChange={filters.setInStockOnly}
                onShowScancodeChange={filters.setShowScancode}
                onUtrArticleChange={filters.setUtrArticle}
                onRequest={() => {
                  void requestPrimary();
                }}
                onDownload={() => {
                  void downloadPrimary();
                }}
                onImport={() => {
                  void importPrimary();
                }}
                canDownload={Boolean(lifecycle.firstDownloadable)}
                canImport={Boolean(lifecycle.firstImportable)}
                isUtr={filters.isUtr}
                utrFilterMode={filters.utrFilterMode}
                onUtrFilterModeChange={filters.setUtrFilterMode}
                selectedVisibleBrands={filters.selectedVisibleBrands}
                selectedCategories={filters.selectedCategories}
                selectedModels={filters.selectedModels}
                manualModels={filters.manualModels}
                onManualModelsChange={filters.setManualModels}
                onToggleVisibleBrand={filters.toggleVisibleBrand}
                onToggleCategory={filters.toggleCategory}
                onToggleModel={filters.toggleModel}
                selectedFiltersCount={filters.selectedCount}
                activeCode={scope.activeCode}
                paramsSourceLabel={paramsSourceLabel}
              />

              <SupplierImportProgressPanel
                t={t}
                tErrors={tErrors}
                latestPriceList={lifecycle.latestPriceList}
                latestDownloaded={lifecycle.latestDownloaded}
                latestImported={lifecycle.latestImported}
                latestErrored={lifecycle.latestErrored}
                workspace={scope.workspace}
                isUtr={filters.isUtr}
                cooldownCanRun={cooldownCanRun}
                cooldownSecondsLeft={cooldownSecondsLeft}
              />
            </section>

            <SupplierImportRunsTable
              t={t}
              rows={rows}
              isLoading={priceListsLoading}
              error={priceListsError}
              tokenReady={tokenReady}
              cooldownCanRun={cooldownCanRun}
              onRefresh={() => {
                void refetchPriceLists();
              }}
              onRowRequest={(item) => {
                void actions.requestFromRow(item);
              }}
              onRowDownload={(item) => {
                void actions.downloadFromRow(item);
              }}
              onRowImport={(item) => {
                void actions.importFromRow(item);
              }}
              onRowDelete={(item) => {
                void actions.deleteFromRow(item);
              }}
            />

            <SupplierImportFooter
              t={t}
              suppliersCount={scope.suppliers?.length ?? 0}
            />
          </div>
        ) : null}
      </AsyncState>
    </section>
  );
}
