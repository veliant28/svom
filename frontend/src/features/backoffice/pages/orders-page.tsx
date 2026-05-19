"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";

import { OrderDeleteModal } from "@/features/backoffice/components/orders/order-delete-modal";
import { OrderHistoryModal } from "@/features/backoffice/components/orders/order-history-modal";
import { OrdersFilters } from "@/features/backoffice/components/orders/orders-filters";
import { OrdersTable } from "@/features/backoffice/components/orders/orders-table";
import { OrderSupplierModal } from "@/features/backoffice/components/orders/order-supplier-modal";
import { OrderWaybillModal } from "@/features/backoffice/components/orders/order-waybill-modal";
import { OrderViewModal } from "@/features/backoffice/components/orders/order-view-modal";
import { ReturnsOperationsPanel } from "@/features/backoffice/components/orders/returns-operations-panel";
import { PageHeader } from "@/features/backoffice/components/widgets/page-header";
import { useOrdersPage } from "@/features/backoffice/hooks/use-orders-page";
import { BACKOFFICE_CAPABILITIES, hasBackofficeCapability } from "@/features/backoffice/lib/capabilities";
import { useAuth } from "@/features/auth/hooks/use-auth";

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
    viewPaymentRefreshing,
    viewPaymentCooldown,
    viewMonobankActionLoading,
    viewMonobankFiscalChecks,
    viewReceiptActionLoading,
    canResetToNew,
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
    orderHistoryOpen,
    waybillHistoryOpen,
    historyLoading,
    historyTarget,
    orderHistoryEvents,
    waybillHistoryEvents,
    bulkActions,
    openOrderView,
    closeOrderView,
    runOrderAction,
    issueReceipt,
    syncReceipt,
    openReceipt,
    refreshOrderPayment,
    runMonobankPaymentAction,
    openSupplierModalFromRow,
    openWaybillModalFromRow,
    openOrderHistoryFromRow,
    openWaybillHistoryFromRow,
    closeOrderHistory,
    closeWaybillHistory,
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
  const { user } = useAuth();
  const [mode, setMode] = useState<"orders" | "returns">("orders");
  const [returnsRefreshNonce, setReturnsRefreshNonce] = useState(0);
  const canViewReturns = hasBackofficeCapability(user, BACKOFFICE_CAPABILITIES.returnsView);

  useEffect(() => {
    if (!canViewReturns && mode === "returns") {
      setMode("orders");
    }
  }, [canViewReturns, mode]);

  const switcher = (
    <div
      className="inline-flex items-center gap-2 rounded-xl border p-1"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
      role="tablist"
      aria-label={t("returns.title")}
    >
      <button
        type="button"
        role="tab"
        aria-selected={mode === "orders"}
        className="inline-flex h-10 items-center rounded-lg border px-4 text-sm font-semibold transition-colors"
        style={{
          borderColor: mode === "orders" ? "#16a34a" : "var(--border)",
          backgroundColor: mode === "orders" ? "#16a34a" : "var(--surface-2)",
          color: mode === "orders" ? "#ffffff" : "var(--text)",
        }}
        onClick={() => setMode("orders")}
      >
        {t("returns.switch.orders")}
      </button>
      {canViewReturns ? (
        <button
          type="button"
          role="tab"
          aria-selected={mode === "returns"}
          className="inline-flex h-10 items-center rounded-lg border px-4 text-sm font-semibold transition-colors"
          style={{
            borderColor: mode === "returns" ? "#ea580c" : "var(--border)",
            backgroundColor: mode === "returns" ? "#ea580c" : "var(--surface-2)",
            color: mode === "returns" ? "#ffffff" : "var(--text)",
          }}
          onClick={() => setMode("returns")}
        >
          {t("returns.switch.returns")}
        </button>
      ) : null}
    </div>
  );

  return (
    <section>
      <PageHeader
        title={mode === "orders" ? t("orders.title") : t("returns.title")}
        description={mode === "orders" ? t("orders.subtitle") : t("returns.subtitle")}
        switcher={switcher}
        actionsBeforeLogout={(
          <button
            type="button"
            className="inline-flex h-10 items-center gap-2 rounded-md border px-4 text-sm font-semibold transition-colors"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            onClick={() => {
              if (mode === "orders") {
                refreshAll();
              } else {
                setReturnsRefreshNonce((value) => value + 1);
              }
            }}
          >
            <RefreshCw size={16} className="animate-spin" style={{ animationDuration: "2.2s" }} />
            {t("orders.actions.refresh")}
          </button>
        )}
      />

      {mode === "returns" && canViewReturns ? <ReturnsOperationsPanel t={t} refreshNonce={returnsRefreshNonce} /> : null}
      {mode !== "orders" ? null : (
        <>
          <OrdersFilters
            t={t}
            q={filters.q}
            status={filters.status}
            pageSize={filters.pageSize}
            pageSizeOptions={filters.pageSizeOptions}
            onSearchChange={filters.onSearchChange}
            onStatusChange={filters.onStatusChange}
            onPageSizeChange={filters.onPageSizeChange}
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
            onOpenOrderHistory={openOrderHistoryFromRow}
            onOpenWaybillHistory={openWaybillHistoryFromRow}
            onSupplierOrder={openSupplierModalFromRow}
            onDelete={requestDelete}
            onPageChange={filters.setPage}
          />

      <OrderHistoryModal
        isOpen={orderHistoryOpen}
        title={t("orders.history.orderTitle")}
        subtitle={historyTarget ? t("orders.history.subtitle", { number: historyTarget.order_number }) : t("orders.history.subtitleEmpty")}
        locale={locale}
        events={orderHistoryEvents}
        isLoading={historyLoading}
        emptyLabel={t("orders.history.orderEmpty")}
        t={t}
        onClose={closeOrderHistory}
      />

      <OrderHistoryModal
        isOpen={waybillHistoryOpen}
        title={t("orders.history.waybillTitle")}
        subtitle={historyTarget ? t("orders.history.subtitle", { number: historyTarget.order_number }) : t("orders.history.subtitleEmpty")}
        locale={locale}
        events={waybillHistoryEvents}
        isLoading={historyLoading}
        emptyLabel={t("orders.history.waybillEmpty")}
        t={t}
        onClose={closeWaybillHistory}
      />

      <OrderViewModal
        isOpen={viewOpen}
        isLoading={viewLoading}
        order={viewOrder}
        actionLoading={viewActionLoading}
        canResetToNew={canResetToNew}
        paymentRefreshing={viewPaymentRefreshing}
        paymentRefreshDisabled={viewPaymentCooldown}
        monobankActionLoading={viewMonobankActionLoading}
        monobankFiscalChecks={viewMonobankFiscalChecks}
        receiptActionLoading={viewReceiptActionLoading}
        onRunAction={(action) => {
          void runOrderAction(action);
        }}
        onIssueReceipt={() => {
          void issueReceipt();
        }}
        onSyncReceipt={() => {
          void syncReceipt();
        }}
        onOpenReceipt={() => {
          void openReceipt();
        }}
        onRefreshPayment={() => {
          void refreshOrderPayment();
        }}
        onRunMonobankAction={(action, options) => {
          void runMonobankPaymentAction(action, options);
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
        </>
      )}
    </section>
  );
}
