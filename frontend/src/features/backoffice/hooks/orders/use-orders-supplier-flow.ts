import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";

import {
  cancelBackofficeGplSupplierOrder,
  createBackofficeGplSupplierOrder,
  getBackofficeOrderDetail,
  getBackofficeOrderSupplierPayload,
} from "@/features/backoffice/api/orders-api";
import type { BackofficeOrderOperational, BackofficeOrderSupplierPayloadPreview } from "@/features/backoffice/types/orders.types";

type SupplierFlowFeedback = {
  showApiError: (error: unknown, fallbackMessage?: string) => string;
  showSuccess: (message: string) => void;
};

export function useOrdersSupplierFlow({
  token,
  refetch,
  feedback,
}: {
  token: string | null;
  refetch: () => Promise<unknown>;
  feedback: SupplierFlowFeedback;
}) {
  const t = useTranslations("backoffice.common");

  const [supplierOpen, setSupplierOpen] = useState(false);
  const [supplierTarget, setSupplierTarget] = useState<BackofficeOrderOperational | null>(null);
  const [supplierPreview, setSupplierPreview] = useState<BackofficeOrderSupplierPayloadPreview | null>(null);
  const [supplierPreviewLoading, setSupplierPreviewLoading] = useState(false);
  const [supplierSubmitting, setSupplierSubmitting] = useState(false);
  const [supplierCancelling, setSupplierCancelling] = useState(false);
  const [supplierLoadingId, setSupplierLoadingId] = useState<string | null>(null);

  const refreshSupplierPreview = useCallback(async (orderId?: string) => {
    const targetOrderId = orderId || supplierTarget?.id;
    if (!token || !targetOrderId) {
      return;
    }

    setSupplierPreviewLoading(true);
    try {
      const payload = await getBackofficeOrderSupplierPayload(token, { order_id: targetOrderId });
      setSupplierPreview(payload);
    } catch (actionError: unknown) {
      feedback.showApiError(actionError, t("orders.messages.supplierPayloadFailed"));
    } finally {
      setSupplierPreviewLoading(false);
    }
  }, [feedback, supplierTarget?.id, t, token]);

  const openSupplierModalFromRow = useCallback(async (item: BackofficeOrderOperational) => {
    if (!token) {
      return;
    }

    setSupplierLoadingId(item.id);
    try {
      const detail = await getBackofficeOrderDetail(token, item.id);
      setSupplierTarget(detail);
      setSupplierOpen(true);
      await refreshSupplierPreview(detail.id);
    } catch (actionError: unknown) {
      feedback.showApiError(actionError, t("orders.messages.detailFailed"));
    } finally {
      setSupplierLoadingId(null);
    }
  }, [feedback, refreshSupplierPreview, t, token]);

  const closeSupplierModal = useCallback(() => {
    if (supplierSubmitting || supplierCancelling) {
      return;
    }

    setSupplierOpen(false);
    setSupplierTarget(null);
    setSupplierPreview(null);
  }, [supplierCancelling, supplierSubmitting]);

  const submitSupplierOrder = useCallback(async (): Promise<string | null> => {
    if (!token || !supplierTarget || !supplierPreview || supplierSubmitting || supplierCancelling) {
      return null;
    }

    setSupplierSubmitting(true);
    try {
      const payload = await createBackofficeGplSupplierOrder(token, {
        order_id: supplierTarget.id,
        products: supplierPreview.products,
      });
      if (payload.supplier_order_id) {
        feedback.showSuccess(t("orders.messages.supplierOrderCreatedWithId", { id: payload.supplier_order_id }));
      } else {
        feedback.showSuccess(t("orders.messages.supplierOrderCreated"));
      }

      await refetch();
      await refreshSupplierPreview(supplierTarget.id);
      return supplierTarget.id;
    } catch (actionError: unknown) {
      feedback.showApiError(actionError, t("orders.messages.supplierCreateFailed"));
      return null;
    } finally {
      setSupplierSubmitting(false);
    }
  }, [feedback, refetch, refreshSupplierPreview, supplierCancelling, supplierPreview, supplierSubmitting, supplierTarget, t, token]);

  const cancelSupplierOrder = useCallback(async (): Promise<string | null> => {
    if (!token || !supplierTarget || !supplierPreview?.last_supplier_order_id || supplierSubmitting || supplierCancelling) {
      return null;
    }

    setSupplierCancelling(true);
    try {
      await cancelBackofficeGplSupplierOrder(token, {
        order_id: supplierTarget.id,
        supplier_order_id: supplierPreview.last_supplier_order_id,
      });
      feedback.showSuccess(t("orders.messages.supplierOrderCancelled"));
      await refreshSupplierPreview(supplierTarget.id);
      return supplierTarget.id;
    } catch (actionError: unknown) {
      feedback.showApiError(actionError, t("orders.messages.supplierCancelFailed"));
      return null;
    } finally {
      setSupplierCancelling(false);
    }
  }, [feedback, refreshSupplierPreview, supplierCancelling, supplierPreview?.last_supplier_order_id, supplierSubmitting, supplierTarget, t, token]);

  const syncSupplierTarget = useCallback(async (orderId: string) => {
    if (!token || !supplierTarget || supplierTarget.id !== orderId) {
      return;
    }

    const fresh = await getBackofficeOrderDetail(token, orderId);
    setSupplierTarget(fresh);
  }, [supplierTarget, token]);

  const handleDeletedOrders = useCallback((deletedIds: string[]) => {
    if (!supplierTarget || !deletedIds.includes(supplierTarget.id)) {
      return;
    }

    setSupplierOpen(false);
    setSupplierTarget(null);
    setSupplierPreview(null);
  }, [supplierTarget]);

  return {
    supplierOpen,
    supplierTarget,
    supplierPreview,
    supplierPreviewLoading,
    supplierSubmitting,
    supplierCancelling,
    supplierLoadingId,
    openSupplierModalFromRow,
    closeSupplierModal,
    refreshSupplierPreview,
    submitSupplierOrder,
    cancelSupplierOrder,
    syncSupplierTarget,
    handleDeletedOrders,
  };
}
