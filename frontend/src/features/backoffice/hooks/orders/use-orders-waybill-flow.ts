import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";

import {
  createBackofficeOrderWaybill,
  deleteBackofficeOrderWaybill,
  getBackofficeOrderDetail,
  getBackofficeOrderWaybill,
  listBackofficeNovaPoshtaSenderProfiles,
  printBackofficeOrderWaybill,
  syncBackofficeOrderWaybill,
  updateBackofficeOrderWaybill,
} from "@/features/backoffice/api/orders-api";
import type { WaybillFormPayload } from "@/features/backoffice/lib/orders/waybill-form";
import type { BackofficeOrderOperational } from "@/features/backoffice/types/orders.types";
import type {
  BackofficeNovaPoshtaSenderProfile,
  BackofficeOrderNovaPoshtaWaybill,
  BackofficeOrderNovaPoshtaWaybillSummary,
} from "@/features/backoffice/types/nova-poshta.types";

type OrdersWaybillFeedback = {
  showApiError: (error: unknown, fallbackMessage?: string) => string;
  showSuccess: (message: string) => void;
};

const EMPTY_SUMMARY: BackofficeOrderNovaPoshtaWaybillSummary = {
  exists: false,
  is_deleted: false,
  np_number: "",
  status_code: "",
  status_text: "",
  has_sync_error: false,
};

export function useOrdersWaybillFlow({
  token,
  refetch,
  feedback,
}: {
  token: string | null;
  refetch: () => Promise<unknown>;
  feedback: OrdersWaybillFeedback;
}) {
  const t = useTranslations("backoffice.common");

  const [waybillOpen, setWaybillOpen] = useState(false);
  const [waybillTarget, setWaybillTarget] = useState<BackofficeOrderOperational | null>(null);
  const [waybillOrderLoadingId, setWaybillOrderLoadingId] = useState<string | null>(null);
  const [waybillLoading, setWaybillLoading] = useState(false);
  const [waybillSubmitting, setWaybillSubmitting] = useState(false);
  const [waybillSyncing, setWaybillSyncing] = useState(false);
  const [waybillDeleting, setWaybillDeleting] = useState(false);

  const [waybill, setWaybill] = useState<BackofficeOrderNovaPoshtaWaybill | null>(null);
  const [waybillSummary, setWaybillSummary] = useState<BackofficeOrderNovaPoshtaWaybillSummary>(EMPTY_SUMMARY);
  const [senderProfiles, setSenderProfiles] = useState<BackofficeNovaPoshtaSenderProfile[]>([]);

  const refreshWaybillState = useCallback(async (orderId?: string) => {
    const targetOrderId = orderId || waybillTarget?.id;
    if (!token || !targetOrderId) {
      return;
    }

    setWaybillLoading(true);
    try {
      const [waybillPayload, senders] = await Promise.all([
        getBackofficeOrderWaybill(token, targetOrderId),
        listBackofficeNovaPoshtaSenderProfiles(token),
      ]);
      setWaybill(waybillPayload.waybill);
      setWaybillSummary(waybillPayload.summary);
      setSenderProfiles(senders);
    } catch (error: unknown) {
      feedback.showApiError(error, t("orders.messages.waybillLoadFailed"));
    } finally {
      setWaybillLoading(false);
    }
  }, [feedback, t, token, waybillTarget?.id]);

  const openWaybillModalFromRow = useCallback(async (item: BackofficeOrderOperational) => {
    if (!token) {
      return;
    }

    setWaybillOrderLoadingId(item.id);
    try {
      const detail = await getBackofficeOrderDetail(token, item.id);
      setWaybillTarget(detail);
      setWaybillOpen(true);
      await refreshWaybillState(detail.id);
    } catch (error: unknown) {
      feedback.showApiError(error, t("orders.messages.detailFailed"));
    } finally {
      setWaybillOrderLoadingId(null);
    }
  }, [feedback, refreshWaybillState, t, token]);

  const closeWaybillModal = useCallback(() => {
    if (waybillSubmitting || waybillSyncing || waybillDeleting) {
      return;
    }

    setWaybillOpen(false);
    setWaybillTarget(null);
    setWaybill(null);
    setWaybillSummary(EMPTY_SUMMARY);
    setSenderProfiles([]);
  }, [waybillDeleting, waybillSubmitting, waybillSyncing]);

  const saveWaybill = useCallback(async (payload: WaybillFormPayload) => {
    if (!token || !waybillTarget) {
      return;
    }

    setWaybillSubmitting(true);
    try {
      const requestPayload: Record<string, unknown> = { ...payload };
      const optionalKeys = [
        "recipient_city_label",
        "recipient_address_ref",
        "recipient_address_label",
        "recipient_counterparty_ref",
        "recipient_contact_ref",
        "recipient_street_ref",
        "recipient_street_label",
        "recipient_house",
        "recipient_apartment",
        "volume_general",
        "pack_ref",
        "pack_refs",
        "volumetric_width",
        "volumetric_length",
        "volumetric_height",
        "afterpayment_amount",
      ] as const;
      for (const key of optionalKeys) {
        const value = requestPayload[key];
        if (typeof value === "string" && !value.trim()) {
          delete requestPayload[key];
          continue;
        }
        if (Array.isArray(value) && value.length === 0) {
          delete requestPayload[key];
        }
      }

      const next = waybill?.id
        ? await updateBackofficeOrderWaybill(token, waybillTarget.id, requestPayload as WaybillFormPayload)
        : await createBackofficeOrderWaybill(token, waybillTarget.id, requestPayload as WaybillFormPayload);

      setWaybill(next);
      setWaybillSummary({
        exists: true,
        is_deleted: next.is_deleted,
        np_number: next.np_number,
        status_code: next.status_code,
        status_text: next.status_text,
        has_sync_error: Boolean(next.last_sync_error),
      });

      feedback.showSuccess(
        waybill?.id ? t("orders.messages.waybillUpdated") : t("orders.messages.waybillCreated"),
      );
      await refetch();
    } catch (error: unknown) {
      feedback.showApiError(error, t("orders.messages.waybillSaveFailed"));
    } finally {
      setWaybillSubmitting(false);
    }
  }, [feedback, refetch, t, token, waybill?.id, waybillTarget]);

  const syncWaybill = useCallback(async () => {
    if (!token || !waybillTarget || !waybill?.id) {
      return;
    }

    setWaybillSyncing(true);
    try {
      const next = await syncBackofficeOrderWaybill(token, waybillTarget.id);
      setWaybill(next);
      setWaybillSummary({
        exists: true,
        is_deleted: next.is_deleted,
        np_number: next.np_number,
        status_code: next.status_code,
        status_text: next.status_text,
        has_sync_error: Boolean(next.last_sync_error),
      });
      feedback.showSuccess(t("orders.messages.waybillSynced"));
      await refetch();
    } catch (error: unknown) {
      feedback.showApiError(error, t("orders.messages.waybillSyncFailed"));
    } finally {
      setWaybillSyncing(false);
    }
  }, [feedback, refetch, t, token, waybill?.id, waybillTarget]);

  const deleteWaybill = useCallback(async () => {
    if (!token || !waybillTarget || !waybill?.id) {
      return;
    }

    setWaybillDeleting(true);
    try {
      const next = await deleteBackofficeOrderWaybill(token, waybillTarget.id);
      setWaybill(next);
      setWaybillSummary({
        exists: false,
        is_deleted: true,
        np_number: "",
        status_code: next.status_code,
        status_text: next.status_text,
        has_sync_error: Boolean(next.last_sync_error),
      });
      feedback.showSuccess(t("orders.messages.waybillDeleted"));
      await refetch();
    } catch (error: unknown) {
      feedback.showApiError(error, t("orders.messages.waybillDeleteFailed"));
    } finally {
      setWaybillDeleting(false);
    }
  }, [feedback, refetch, t, token, waybill?.id, waybillTarget]);

  const printWaybill = useCallback(async (format: "html" | "pdf") => {
    if (!token || !waybillTarget || !waybill?.id) {
      return;
    }

    try {
      const blob = await printBackofficeOrderWaybill(token, waybillTarget.id, format);
      const objectUrl = URL.createObjectURL(blob);
      if (format === "pdf") {
        const link = document.createElement("a");
        link.href = objectUrl;
        link.download = `np-waybill-${waybill.np_number || waybill.id}.pdf`;
        link.click();
      } else {
        window.open(objectUrl, "_blank", "noopener,noreferrer");
      }
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 30_000);
    } catch (error: unknown) {
      feedback.showApiError(error, t("orders.messages.waybillPrintFailed"));
    }
  }, [feedback, t, token, waybill?.id, waybill?.np_number, waybillTarget]);

  const handleDeletedOrders = useCallback((deletedIds: string[]) => {
    if (!waybillTarget || !deletedIds.includes(waybillTarget.id)) {
      return;
    }

    setWaybillOpen(false);
    setWaybillTarget(null);
    setWaybill(null);
    setWaybillSummary(EMPTY_SUMMARY);
    setSenderProfiles([]);
  }, [waybillTarget]);

  return {
    waybillOpen,
    waybillTarget,
    waybillOrderLoadingId,
    waybillLoading,
    waybillSubmitting,
    waybillSyncing,
    waybillDeleting,
    waybill,
    waybillSummary,
    senderProfiles,
    openWaybillModalFromRow,
    closeWaybillModal,
    refreshWaybillState,
    saveWaybill,
    syncWaybill,
    deleteWaybill,
    printWaybill,
    handleDeletedOrders,
  };
}
