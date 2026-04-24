import { useCallback, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { useOrdersActions } from "@/features/backoffice/hooks/orders/use-orders-actions";
import { useOrdersBulkActions } from "@/features/backoffice/hooks/orders/use-orders-bulk-actions";
import { useOrdersDerivedState } from "@/features/backoffice/hooks/orders/use-orders-derived-state";
import { useOrdersFilters } from "@/features/backoffice/hooks/orders/use-orders-filters";
import { useOrdersPageData } from "@/features/backoffice/hooks/orders/use-orders-page-data";
import { useOrdersSupplierFlow } from "@/features/backoffice/hooks/orders/use-orders-supplier-flow";
import { useOrdersWaybillFlow } from "@/features/backoffice/hooks/orders/use-orders-waybill-flow";

export function useOrdersPage() {
  const t = useTranslations("backoffice.common");
  const locale = useLocale();
  const { showApiError, showSuccess, showWarning, showInfo } = useBackofficeFeedback();

  const filters = useOrdersFilters();
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  const removeSelectedIds = useCallback((deletedIds: string[]) => {
    setSelectedIds((prev) => prev.filter((id) => !deletedIds.includes(id)));
  }, []);

  const { token, rows, totalCount, pagesCount, isLoading, error, refetch } = useOrdersPageData(filters);

  const supplierFlow = useOrdersSupplierFlow({
    token,
    refetch,
    feedback: { showApiError, showSuccess },
  });
  const waybillFlow = useOrdersWaybillFlow({
    token,
    refetch,
    feedback: { showApiError, showSuccess },
  });

  const orderActions = useOrdersActions({
    token,
    refetch,
    feedback: { showApiError, showSuccess, showWarning, showInfo },
    onAfterAction: supplierFlow.syncSupplierTarget,
    onSelectionDeleted: removeSelectedIds,
    onSupplierDeleted: (deletedIds) => {
      supplierFlow.handleDeletedOrders(deletedIds);
      waybillFlow.handleDeletedOrders(deletedIds);
    },
  });

  const handleAfterBulkDelete = useCallback((deletedIds: string[]) => {
    removeSelectedIds(deletedIds);
    orderActions.handleDeletedOrders(deletedIds);
    supplierFlow.handleDeletedOrders(deletedIds);
    waybillFlow.handleDeletedOrders(deletedIds);
  }, [orderActions, removeSelectedIds, supplierFlow, waybillFlow]);

  const bulkActions = useOrdersBulkActions({
    token,
    rows,
    selectedIds,
    setSelectedIds,
    feedback: { showSuccess, showApiError, showWarning },
    onAfterDelete: handleAfterBulkDelete,
    refetch,
  });

  const submitSupplierOrder = useCallback(async () => {
    const changedOrderId = await supplierFlow.submitSupplierOrder();
    if (changedOrderId && orderActions.viewOrderId === changedOrderId) {
      await orderActions.loadOrderDetail(changedOrderId);
    }
  }, [orderActions, supplierFlow]);

  const cancelSupplierOrder = useCallback(async () => {
    const changedOrderId = await supplierFlow.cancelSupplierOrder();
    if (changedOrderId && orderActions.viewOrderId === changedOrderId) {
      await orderActions.loadOrderDetail(changedOrderId);
    }
  }, [orderActions, supplierFlow]);

  const { refreshAll } = useOrdersDerivedState({
    refetch,
    viewOrderId: orderActions.viewOrderId,
    loadOrderDetail: orderActions.loadOrderDetail,
    supplierOpen: supplierFlow.supplierOpen,
    supplierTargetId: supplierFlow.supplierTarget?.id ?? null,
    refreshSupplierPreview: supplierFlow.refreshSupplierPreview,
    waybillOpen: waybillFlow.waybillOpen,
    waybillTargetId: waybillFlow.waybillTarget?.id ?? null,
    refreshWaybillState: waybillFlow.refreshWaybillState,
  });

  return {
    t,
    locale,
    token,
    filters,
    rows,
    totalCount,
    pagesCount,
    isLoading,
    error,
    deleteTarget: orderActions.deleteTarget,
    deletingId: orderActions.deletingId,
    openingId: orderActions.openingId,
    supplierLoadingId: supplierFlow.supplierLoadingId,
    waybillLoadingId: waybillFlow.waybillOrderLoadingId,
    viewOpen: orderActions.viewOpen,
    viewOrder: orderActions.viewOrder,
    viewLoading: orderActions.viewLoading,
    viewActionLoading: orderActions.viewActionLoading,
    viewPaymentRefreshing: orderActions.viewPaymentRefreshing,
    viewPaymentCooldown: orderActions.viewPaymentCooldown,
    viewMonobankActionLoading: orderActions.viewMonobankActionLoading,
    viewMonobankFiscalChecks: orderActions.viewMonobankFiscalChecks,
    viewReceiptActionLoading: orderActions.viewReceiptActionLoading,
    canResetToNew: orderActions.canResetToNew,
    supplierOpen: supplierFlow.supplierOpen,
    supplierTarget: supplierFlow.supplierTarget,
    supplierPreview: supplierFlow.supplierPreview,
    supplierPreviewLoading: supplierFlow.supplierPreviewLoading,
    supplierSubmitting: supplierFlow.supplierSubmitting,
    supplierCancelling: supplierFlow.supplierCancelling,
    waybillOpen: waybillFlow.waybillOpen,
    waybillTarget: waybillFlow.waybillTarget,
    waybill: waybillFlow.waybill,
    waybillSummary: waybillFlow.waybillSummary,
    waybillLoading: waybillFlow.waybillLoading,
    waybillSubmitting: waybillFlow.waybillSubmitting,
    waybillSyncing: waybillFlow.waybillSyncing,
    waybillDeleting: waybillFlow.waybillDeleting,
    waybillSenderProfiles: waybillFlow.senderProfiles,
    bulkActions,
    openOrderView: orderActions.openOrderView,
    closeOrderView: orderActions.closeOrderView,
    runOrderAction: orderActions.runOrderAction,
    issueReceipt: orderActions.issueReceipt,
    syncReceipt: orderActions.syncReceipt,
    openReceipt: orderActions.openReceipt,
    refreshOrderPayment: orderActions.refreshOrderPayment,
    runMonobankPaymentAction: orderActions.runMonobankPaymentAction,
    openSupplierModalFromRow: supplierFlow.openSupplierModalFromRow,
    openWaybillModalFromRow: waybillFlow.openWaybillModalFromRow,
    closeSupplierModal: supplierFlow.closeSupplierModal,
    closeWaybillModal: waybillFlow.closeWaybillModal,
    refreshSupplierPreview: supplierFlow.refreshSupplierPreview,
    refreshWaybillState: waybillFlow.refreshWaybillState,
    submitSupplierOrder,
    cancelSupplierOrder,
    saveWaybill: waybillFlow.saveWaybill,
    syncWaybill: waybillFlow.syncWaybill,
    deleteWaybill: waybillFlow.deleteWaybill,
    printWaybill: waybillFlow.printWaybill,
    requestDelete: orderActions.requestDelete,
    closeDelete: orderActions.closeDelete,
    runSingleDelete: orderActions.runSingleDelete,
    refreshAll,
  };
}
