import { useCallback } from "react";

export function useOrdersDerivedState({
  refetch,
  viewOrderId,
  loadOrderDetail,
  supplierOpen,
  supplierTargetId,
  refreshSupplierPreview,
  waybillOpen,
  waybillTargetId,
  refreshWaybillState,
}: {
  refetch: () => Promise<unknown>;
  viewOrderId: string | null;
  loadOrderDetail: (orderId: string) => Promise<unknown>;
  supplierOpen: boolean;
  supplierTargetId: string | null;
  refreshSupplierPreview: (orderId?: string) => Promise<void>;
  waybillOpen: boolean;
  waybillTargetId: string | null;
  refreshWaybillState: (orderId?: string) => Promise<void>;
}) {
  const refreshAll = useCallback(() => {
    void refetch();
    if (viewOrderId) {
      void loadOrderDetail(viewOrderId);
    }
    if (supplierOpen && supplierTargetId) {
      void refreshSupplierPreview(supplierTargetId);
    }
    if (waybillOpen && waybillTargetId) {
      void refreshWaybillState(waybillTargetId);
    }
  }, [loadOrderDetail, refetch, refreshSupplierPreview, supplierOpen, supplierTargetId, viewOrderId, waybillOpen, waybillTargetId, refreshWaybillState]);

  return {
    refreshAll,
  };
}
