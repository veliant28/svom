import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import {
  cancelBackofficeOrder,
  confirmBackofficeOrder,
  deleteBackofficeOrder,
  getBackofficeOrderDetail,
  markBackofficeOrderCompleted,
  markBackofficeOrderReadyToShip,
  markBackofficeOrderShipped,
  resetBackofficeOrderToNew,
} from "@/features/backoffice/api/orders-api";
import { refreshBackofficeOrderPayment, runBackofficeOrderMonobankPaymentAction } from "@/features/backoffice/api/payment-api";
import { useAuth } from "@/features/auth/hooks/use-auth";
import type {
  BackofficeMonobankFiscalCheck,
  BackofficeMonobankPaymentAction,
  BackofficeOrderOperational,
} from "@/features/backoffice/types/orders.types";

export type OrderViewAction = "confirm" | "ready" | "ship" | "complete" | "reset" | "cancel";

type OrdersActionsFeedback = {
  showApiError: (error: unknown, fallbackMessage?: string) => string;
  showSuccess: (message: string) => void;
  showWarning?: (message: string) => void;
  showInfo?: (message: string) => void;
};

const PAYMENT_REFRESH_COOLDOWN_SECONDS = 10;

function extractCooldownSecondsFromMessage(message: string): number | null {
  const match = message.match(/(\d{1,6})\s*(sec|secs|second|seconds|сек|секунд|с)\b/i);
  if (!match) {
    return null;
  }
  const value = Number(match[1]);
  if (!Number.isFinite(value) || value <= 0) {
    return null;
  }
  return Math.ceil(value);
}

export function useOrdersActions({
  token,
  refetch,
  feedback,
  onAfterAction,
  onSelectionDeleted,
  onSupplierDeleted,
}: {
  token: string | null;
  refetch: () => Promise<unknown>;
  feedback: OrdersActionsFeedback;
  onAfterAction?: (orderId: string) => Promise<void>;
  onSelectionDeleted?: (deletedIds: string[]) => void;
  onSupplierDeleted?: (deletedIds: string[]) => void;
}) {
  const t = useTranslations("backoffice.common");
  const { user } = useAuth();

  const [viewOpen, setViewOpen] = useState(false);
  const [viewOrderId, setViewOrderId] = useState<string | null>(null);
  const [viewOrder, setViewOrder] = useState<BackofficeOrderOperational | null>(null);
  const [viewLoading, setViewLoading] = useState(false);
  const [openingId, setOpeningId] = useState<string | null>(null);
  const [viewActionLoading, setViewActionLoading] = useState<OrderViewAction | null>(null);
  const [viewPaymentRefreshing, setViewPaymentRefreshing] = useState(false);
  const [viewPaymentCooldown, setViewPaymentCooldown] = useState(false);
  const [viewMonobankActionLoading, setViewMonobankActionLoading] = useState<BackofficeMonobankPaymentAction | null>(null);
  const [viewMonobankFiscalChecks, setViewMonobankFiscalChecks] = useState<BackofficeMonobankFiscalCheck[]>([]);
  const cooldownTimeoutRef = useRef<number | null>(null);

  const [deleteTarget, setDeleteTarget] = useState<BackofficeOrderOperational | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const canResetToNew = Boolean(
    user && user.groups.some(
      (group) => group.name === "Backoffice Role: administrator" || group.name === "Backoffice Role: manager",
    ),
  );

  const startPaymentRefreshCooldown = useCallback((seconds: number) => {
    if (cooldownTimeoutRef.current) {
      window.clearTimeout(cooldownTimeoutRef.current);
    }
    setViewPaymentCooldown(true);
    cooldownTimeoutRef.current = window.setTimeout(() => {
      setViewPaymentCooldown(false);
      cooldownTimeoutRef.current = null;
    }, Math.max(1, seconds) * 1000);
  }, []);

  useEffect(() => (
    () => {
      if (cooldownTimeoutRef.current) {
        window.clearTimeout(cooldownTimeoutRef.current);
        cooldownTimeoutRef.current = null;
      }
    }
  ), []);

  const loadOrderDetail = useCallback(async (orderId: string) => {
    if (!token) {
      return null;
    }

    setViewLoading(true);
    try {
      const detail = await getBackofficeOrderDetail(token, orderId);
      setViewOrder(detail);
      return detail;
    } catch (actionError: unknown) {
      feedback.showApiError(actionError, t("orders.messages.detailFailed"));
      return null;
    } finally {
      setViewLoading(false);
    }
  }, [feedback, t, token]);

  const openOrderView = useCallback(async (item: BackofficeOrderOperational) => {
    setViewOpen(true);
    setViewOrderId(item.id);
    setViewMonobankFiscalChecks([]);
    setViewMonobankActionLoading(null);
    setOpeningId(item.id);
    await loadOrderDetail(item.id);
    setOpeningId(null);
  }, [loadOrderDetail]);

  const closeOrderView = useCallback(() => {
    setViewOpen(false);
    setViewOrderId(null);
    setViewOrder(null);
    setViewActionLoading(null);
    setViewMonobankActionLoading(null);
    setViewMonobankFiscalChecks([]);
  }, []);

  const runOrderAction = useCallback(async (action: OrderViewAction) => {
    if (!token || !viewOrder || viewActionLoading) {
      return;
    }

    setViewActionLoading(action);
    try {
      if (action === "confirm") {
        await confirmBackofficeOrder(token, { order_id: viewOrder.id });
        feedback.showSuccess(t("orders.messages.processing"));
      } else if (action === "ready") {
        await markBackofficeOrderReadyToShip(token, { order_id: viewOrder.id });
        feedback.showSuccess(t("orders.messages.readyForShipment"));
      } else if (action === "ship") {
        await markBackofficeOrderShipped(token, { order_id: viewOrder.id });
        feedback.showSuccess(t("orders.messages.shipped"));
      } else if (action === "complete") {
        await markBackofficeOrderCompleted(token, { order_id: viewOrder.id });
        feedback.showSuccess(t("orders.messages.completed"));
      } else if (action === "reset") {
        await resetBackofficeOrderToNew(token, { order_id: viewOrder.id });
        feedback.showSuccess(t("orders.messages.resetToNew"));
      } else if (action === "cancel") {
        await cancelBackofficeOrder(token, { order_id: viewOrder.id, reason_code: "supplier_shortage" });
        feedback.showSuccess(t("orders.messages.cancelled"));
      }

      await refetch();
      await loadOrderDetail(viewOrder.id);
      if (onAfterAction) {
        await onAfterAction(viewOrder.id);
      }
    } catch (actionError: unknown) {
      feedback.showApiError(actionError, t("orders.messages.actionFailed"));
    } finally {
      setViewActionLoading(null);
    }
  }, [feedback, loadOrderDetail, onAfterAction, refetch, t, token, viewActionLoading, viewOrder]);

  const requestDelete = useCallback((item: BackofficeOrderOperational) => {
    setDeleteTarget(item);
  }, []);

  const closeDelete = useCallback(() => {
    if (!deletingId) {
      setDeleteTarget(null);
    }
  }, [deletingId]);

  const handleDeletedOrders = useCallback((deletedIds: string[]) => {
    if (viewOrderId && deletedIds.includes(viewOrderId)) {
      closeOrderView();
    }

    if (deleteTarget && deletedIds.includes(deleteTarget.id)) {
      setDeleteTarget(null);
    }
  }, [closeOrderView, deleteTarget, viewOrderId]);

  const runSingleDelete = useCallback(async () => {
    if (!token || !deleteTarget || deletingId) {
      return;
    }

    const deletedId = deleteTarget.id;
    setDeletingId(deletedId);
    try {
      await deleteBackofficeOrder(token, { order_id: deletedId });
      feedback.showSuccess(t("orders.messages.deleted"));
      handleDeletedOrders([deletedId]);
      if (onSelectionDeleted) {
        onSelectionDeleted([deletedId]);
      }
      if (onSupplierDeleted) {
        onSupplierDeleted([deletedId]);
      }
      setDeleteTarget(null);
      await refetch();
    } catch (actionError: unknown) {
      feedback.showApiError(actionError, t("orders.messages.deleteFailed"));
    } finally {
      setDeletingId(null);
    }
  }, [deleteTarget, deletingId, feedback, handleDeletedOrders, onSelectionDeleted, onSupplierDeleted, refetch, t, token]);

  const refreshOrderPayment = useCallback(async () => {
    if (!token || !viewOrder || viewPaymentRefreshing) {
      return;
    }
    if (viewPaymentCooldown) {
      feedback.showWarning?.(t("toast.errors.cooldownSeconds", { seconds: PAYMENT_REFRESH_COOLDOWN_SECONDS }));
      return;
    }

    setViewPaymentRefreshing(true);
    try {
      const payment = await refreshBackofficeOrderPayment(token, viewOrder.id);
      setViewOrder((prev) => {
        if (!prev) {
          return prev;
        }
        return { ...prev, payment };
      });
      feedback.showSuccess(t("orders.messages.paymentRefreshed"));
      startPaymentRefreshCooldown(PAYMENT_REFRESH_COOLDOWN_SECONDS);
    } catch (error: unknown) {
      const message = feedback.showApiError(error, t("orders.messages.paymentRefreshFailed"));
      if (/слишком рано|too early|cooldown|rate limit|429/i.test(message)) {
        const seconds = extractCooldownSecondsFromMessage(message) ?? PAYMENT_REFRESH_COOLDOWN_SECONDS;
        startPaymentRefreshCooldown(seconds);
      }
    } finally {
      setViewPaymentRefreshing(false);
    }
  }, [feedback, startPaymentRefreshCooldown, t, token, viewOrder, viewPaymentCooldown, viewPaymentRefreshing]);

  const runMonobankPaymentAction = useCallback(async (
    action: BackofficeMonobankPaymentAction,
    options?: { amountMinor?: number },
  ) => {
    if (!token || !viewOrder || viewMonobankActionLoading) {
      return;
    }

    const provider = (viewOrder.payment?.provider || "").trim().toLowerCase();
    if (provider !== "monobank") {
      feedback.showWarning?.(t("orders.messages.monobankActionNotAvailable"));
      return;
    }

    setViewMonobankActionLoading(action);
    try {
      const amount = typeof options?.amountMinor === "number" ? Math.trunc(options.amountMinor) : undefined;
      const result = await runBackofficeOrderMonobankPaymentAction(token, viewOrder.id, {
        action,
        ...(amount && amount > 0 ? { amount } : {}),
      });

      setViewOrder((prev) => {
        if (!prev) {
          return prev;
        }
        return { ...prev, payment: result.payment };
      });

      if (action === "fiscal_checks") {
        setViewMonobankFiscalChecks(result.fiscal_checks || []);
        feedback.showInfo?.(t("orders.messages.paymentFiscalChecksLoaded", { count: result.fiscal_checks.length }));
      } else if (action === "cancel") {
        feedback.showSuccess(t("orders.messages.paymentCancelled"));
      } else if (action === "remove") {
        feedback.showSuccess(t("orders.messages.paymentInvoiceRemoved"));
      } else if (action === "finalize") {
        feedback.showSuccess(t("orders.messages.paymentFinalized"));
      } else if (action === "refresh") {
        feedback.showSuccess(t("orders.messages.paymentRefreshed"));
      }

      await refetch();
    } catch (error: unknown) {
      feedback.showApiError(error, t("orders.messages.monobankActionFailed"));
    } finally {
      setViewMonobankActionLoading(null);
    }
  }, [feedback, refetch, t, token, viewMonobankActionLoading, viewOrder]);

  return {
    viewOpen,
    viewOrderId,
    viewOrder,
    viewLoading,
    openingId,
    viewActionLoading,
    viewPaymentRefreshing,
    viewPaymentCooldown,
    viewMonobankActionLoading,
    viewMonobankFiscalChecks,
    canResetToNew,
    deleteTarget,
    deletingId,
    loadOrderDetail,
    openOrderView,
    closeOrderView,
    runOrderAction,
    requestDelete,
    closeDelete,
    handleDeletedOrders,
    runSingleDelete,
    refreshOrderPayment,
    runMonobankPaymentAction,
  };
}
