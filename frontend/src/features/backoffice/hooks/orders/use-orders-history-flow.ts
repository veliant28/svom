import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import { getBackofficeOrderHistory, getBackofficeOrderWaybillHistory } from "@/features/backoffice/api/orders-api";
import type { BackofficeOrderHistoryEvent, BackofficeOrderOperational } from "@/features/backoffice/types/orders.types";

const HISTORY_POLL_INTERVAL_MS = 12000;

type HistoryKind = "order" | "waybill";

type HistoryFlowFeedback = {
  showApiError: (error: unknown, fallbackMessage?: string) => string;
  showInfo: (message: string) => void;
};

export function useOrdersHistoryFlow({
  token,
  feedback,
}: {
  token: string | null;
  feedback: HistoryFlowFeedback;
}) {
  const t = useTranslations("backoffice.common");

  const [historyTarget, setHistoryTarget] = useState<BackofficeOrderOperational | null>(null);
  const [orderHistoryOpen, setOrderHistoryOpen] = useState(false);
  const [waybillHistoryOpen, setWaybillHistoryOpen] = useState(false);
  const [orderHistoryLoading, setOrderHistoryLoading] = useState(false);
  const [waybillHistoryLoading, setWaybillHistoryLoading] = useState(false);
  const [orderHistoryEvents, setOrderHistoryEvents] = useState<BackofficeOrderHistoryEvent[]>([]);
  const [waybillHistoryEvents, setWaybillHistoryEvents] = useState<BackofficeOrderHistoryEvent[]>([]);

  const inFlightRef = useRef<Record<HistoryKind, boolean>>({ order: false, waybill: false });
  const orderEventsRef = useRef<BackofficeOrderHistoryEvent[]>([]);
  const waybillEventsRef = useRef<BackofficeOrderHistoryEvent[]>([]);

  useEffect(() => {
    orderEventsRef.current = orderHistoryEvents;
  }, [orderHistoryEvents]);

  useEffect(() => {
    waybillEventsRef.current = waybillHistoryEvents;
  }, [waybillHistoryEvents]);

  const loadHistory = useCallback(async (
    kind: HistoryKind,
    orderId: string,
    options?: { silent?: boolean; notifyOnNew?: boolean },
  ) => {
    if (!token || !orderId) {
      return;
    }
    if (inFlightRef.current[kind]) {
      return;
    }

    const silent = Boolean(options?.silent);
    const notifyOnNew = Boolean(options?.notifyOnNew);
    const setLoading = kind === "order" ? setOrderHistoryLoading : setWaybillHistoryLoading;
    const setEvents = kind === "order" ? setOrderHistoryEvents : setWaybillHistoryEvents;
    const prevEvents = kind === "order" ? orderEventsRef.current : waybillEventsRef.current;

    inFlightRef.current[kind] = true;
    if (!silent) {
      setLoading(true);
    }
    try {
      const response = kind === "order"
        ? await getBackofficeOrderHistory(token, orderId)
        : await getBackofficeOrderWaybillHistory(token, orderId);
      const nextEvents = Array.isArray(response.results) ? response.results : [];

      const hasNewEvent = notifyOnNew
        && prevEvents.length > 0
        && nextEvents.length > 0
        && nextEvents[0].id !== prevEvents[0].id;

      setEvents(nextEvents);

      if (hasNewEvent) {
        feedback.showInfo(
          kind === "order"
            ? t("orders.messages.historyUpdatedOrder")
            : t("orders.messages.historyUpdatedWaybill"),
        );
      }
    } catch (error: unknown) {
      if (!silent) {
        feedback.showApiError(error, t("orders.messages.historyLoadFailed"));
      }
    } finally {
      if (!silent) {
        setLoading(false);
      }
      inFlightRef.current[kind] = false;
    }
  }, [feedback, t, token]);

  const openOrderHistoryFromRow = useCallback(async (item: BackofficeOrderOperational) => {
    if (!token) {
      return;
    }
    setHistoryTarget(item);
    setWaybillHistoryOpen(false);
    setWaybillHistoryEvents([]);
    setOrderHistoryOpen(true);
    await loadHistory("order", item.id);
  }, [loadHistory, token]);

  const openWaybillHistoryFromRow = useCallback(async (item: BackofficeOrderOperational) => {
    if (!token) {
      return;
    }
    if (!item.nova_poshta_waybill_exists || !item.nova_poshta_waybill_number) {
      return;
    }
    setHistoryTarget(item);
    setOrderHistoryOpen(false);
    setOrderHistoryEvents([]);
    setWaybillHistoryOpen(true);
    await loadHistory("waybill", item.id);
  }, [loadHistory, token]);

  const closeOrderHistory = useCallback(() => {
    setOrderHistoryOpen(false);
    setOrderHistoryEvents([]);
    setHistoryTarget(null);
  }, []);

  const closeWaybillHistory = useCallback(() => {
    setWaybillHistoryOpen(false);
    setWaybillHistoryEvents([]);
    setHistoryTarget(null);
  }, []);

  useEffect(() => {
    if (!orderHistoryOpen || !historyTarget?.id || !token) {
      return;
    }

    const timerId = window.setInterval(() => {
      if (document.hidden) {
        return;
      }
      void loadHistory("order", historyTarget.id, { silent: true, notifyOnNew: true });
    }, HISTORY_POLL_INTERVAL_MS);

    return () => {
      window.clearInterval(timerId);
    };
  }, [historyTarget?.id, loadHistory, orderHistoryOpen, token]);

  useEffect(() => {
    if (!waybillHistoryOpen || !historyTarget?.id || !token) {
      return;
    }

    const timerId = window.setInterval(() => {
      if (document.hidden) {
        return;
      }
      void loadHistory("waybill", historyTarget.id, { silent: true, notifyOnNew: true });
    }, HISTORY_POLL_INTERVAL_MS);

    return () => {
      window.clearInterval(timerId);
    };
  }, [historyTarget?.id, loadHistory, token, waybillHistoryOpen]);

  const historyLoading = useMemo(() => {
    if (orderHistoryOpen) {
      return orderHistoryLoading;
    }
    if (waybillHistoryOpen) {
      return waybillHistoryLoading;
    }
    return false;
  }, [orderHistoryLoading, orderHistoryOpen, waybillHistoryLoading, waybillHistoryOpen]);

  return {
    orderHistoryOpen,
    waybillHistoryOpen,
    historyLoading,
    historyTarget,
    orderHistoryEvents,
    waybillHistoryEvents,
    openOrderHistoryFromRow,
    openWaybillHistoryFromRow,
    closeOrderHistory,
    closeWaybillHistory,
  };
}
