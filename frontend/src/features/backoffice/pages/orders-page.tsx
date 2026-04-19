"use client";

import { OrderDeleteModal } from "@/features/backoffice/components/orders/order-delete-modal";
import { OrdersFilters } from "@/features/backoffice/components/orders/orders-filters";
import { OrdersTable } from "@/features/backoffice/components/orders/orders-table";
import { OrdersToolbar } from "@/features/backoffice/components/orders/orders-toolbar";
import { OrderSupplierModal } from "@/features/backoffice/components/orders/order-supplier-modal";
import { OrderWaybillModal } from "@/features/backoffice/components/orders/order-waybill-modal";
import { OrderViewModal } from "@/features/backoffice/components/orders/order-view-modal";
import { useOrdersPage } from "@/features/backoffice/hooks/use-orders-page";

export function OrdersPage() {
  const {
    t,
    locale,
    token,
    filters,
    rows,
    totalCount,
    pagesCount,
    isLoading,
    error,
    deleteTarget,
    deletingId,
    openingId,
    waybillLoadingId,
    supplierLoadingId,
    viewOpen,
    viewOrder,
    viewLoading,
    viewActionLoading,
    supplierOpen,
    supplierTarget,
    supplierPreview,
    supplierPreviewLoading,
    supplierSubmitting,
    supplierCancelling,
    waybillOpen,
    waybillTarget,
    waybill,
    waybillLoading,
    waybillSubmitting,
    waybillSyncing,
    waybillDeleting,
    waybillSenderProfiles,
    bulkActions,
    openOrderView,
    closeOrderView,
    runOrderAction,
    openSupplierModalFromRow,
    openWaybillModalFromRow,
    closeSupplierModal,
    closeWaybillModal,
    refreshSupplierPreview,
    refreshWaybillState,
    submitSupplierOrder,
    cancelSupplierOrder,
    saveWaybill,
    syncWaybill,
    deleteWaybill,
    printWaybill,
    requestDelete,
    closeDelete,
    runSingleDelete,
    refreshAll,
  } = useOrdersPage();

  return (
    <section>
      <OrdersToolbar t={t} onRefresh={refreshAll} />

      <OrdersFilters
        t={t}
        q={filters.q}
        status={filters.status}
        onSearchChange={filters.onSearchChange}
        onStatusChange={filters.onStatusChange}
        bulkActionsRef={bulkActions.bulkActionsRef}
        bulkActionsOpen={bulkActions.bulkActionsOpen}
        selectedCount={bulkActions.selectedSet.size}
        bulkRunning={bulkActions.runningDelete}
        onToggleBulkActions={() => {
          bulkActions.setBulkActionsOpen((prev) => !prev);
        }}
        onBulkDelete={() => {
          bulkActions.setBulkActionsOpen(false);
          bulkActions.setBulkDeleteOpen(true);
        }}
      />

      <OrdersTable
        t={t}
        locale={locale}
        rows={rows}
        isLoading={isLoading}
        error={error}
        selectedSet={bulkActions.selectedSet}
        allPageSelected={bulkActions.allPageSelected}
        somePageSelected={bulkActions.somePageSelected}
        deletingId={deletingId}
        openingId={openingId}
        waybillLoadingId={waybillLoadingId}
        supplierLoadingId={supplierLoadingId}
        page={filters.page}
        pagesCount={pagesCount}
        totalCount={totalCount}
        onToggleSelectAllPage={bulkActions.toggleSelectAllPage}
        onToggleSelected={bulkActions.toggleSelected}
        onOpen={openOrderView}
        onWaybill={openWaybillModalFromRow}
        onSupplierOrder={openSupplierModalFromRow}
        onDelete={requestDelete}
        onPageChange={filters.setPage}
      />

      <OrderViewModal
        isOpen={viewOpen}
        isLoading={viewLoading}
        order={viewOrder}
        actionLoading={viewActionLoading}
        onRunAction={(action) => {
          void runOrderAction(action);
        }}
        onClose={closeOrderView}
        t={t}
      />

      <OrderSupplierModal
        isOpen={supplierOpen}
        order={supplierTarget}
        preview={supplierPreview}
        isLoading={supplierPreviewLoading}
        isSubmitting={supplierSubmitting}
        isCancelling={supplierCancelling}
        onRefresh={() => {
          void refreshSupplierPreview();
        }}
        onSubmit={() => {
          void submitSupplierOrder();
        }}
        onCancelSupplierOrder={() => {
          void cancelSupplierOrder();
        }}
        onClose={closeSupplierModal}
        t={t}
      />

      <OrderWaybillModal
        isOpen={waybillOpen}
        token={token}
        locale={locale}
        order={waybillTarget}
        waybill={waybill}
        senderProfiles={waybillSenderProfiles}
        isLoading={waybillLoading}
        isSubmitting={waybillSubmitting}
        isSyncing={waybillSyncing}
        isDeleting={waybillDeleting}
        onRefresh={() => {
          void refreshWaybillState();
        }}
        onSave={(payload) => {
          void saveWaybill(payload);
        }}
        onSync={() => {
          void syncWaybill();
        }}
        onDelete={() => {
          void deleteWaybill();
        }}
        onPrint={(format) => {
          void printWaybill(format);
        }}
        onClose={closeWaybillModal}
        t={t}
      />

      <OrderDeleteModal
        isOpen={Boolean(deleteTarget)}
        isSubmitting={Boolean(deletingId)}
        title={t("orders.modals.delete.title")}
        message={t("orders.modals.delete.singleMessage", { orderNumber: deleteTarget?.order_number ?? "" })}
        confirmLabel={t("orders.actions.delete")}
        onClose={closeDelete}
        onConfirm={() => {
          void runSingleDelete();
        }}
        t={t}
      />

      <OrderDeleteModal
        isOpen={bulkActions.bulkDeleteOpen}
        isSubmitting={bulkActions.runningDelete}
        title={t("orders.modals.delete.bulkTitle")}
        message={t("orders.modals.delete.bulkMessage", { count: bulkActions.selectedSet.size })}
        confirmLabel={t("orders.actions.bulkDelete")}
        onClose={() => {
          if (!bulkActions.runningDelete) {
            bulkActions.setBulkDeleteOpen(false);
          }
        }}
        onConfirm={() => {
          void bulkActions.runBulkDelete();
        }}
        t={t}
      />
    </section>
  );
}
