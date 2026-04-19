import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { useTranslations } from "next-intl";

import { bulkDeleteBackofficeOrders } from "@/features/backoffice/api/orders-api";
import type { BackofficeOrderOperational } from "@/features/backoffice/types/orders.types";

type BackofficeFeedback = {
  showSuccess: (message: string) => void;
  showApiError: (error: unknown, fallbackMessage?: string) => string;
  showWarning: (message: string) => void;
};

export function useOrderBulkActions({
  token,
  rows,
  selectedIds,
  setSelectedIds,
  feedback,
  onAfterDelete,
  refetch,
}: {
  token: string | null;
  rows: BackofficeOrderOperational[];
  selectedIds: string[];
  setSelectedIds: Dispatch<SetStateAction<string[]>>;
  feedback: BackofficeFeedback;
  onAfterDelete: (deletedIds: string[]) => void;
  refetch: () => Promise<unknown>;
}) {
  const t = useTranslations("backoffice.common");

  const [runningDelete, setRunningDelete] = useState(false);
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const [bulkActionsOpen, setBulkActionsOpen] = useState(false);
  const bulkActionsRef = useRef<HTMLDivElement | null>(null);

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const allPageSelected = rows.length > 0 && rows.every((row) => selectedSet.has(row.id));
  const somePageSelected = rows.some((row) => selectedSet.has(row.id));

  const toggleSelected = useCallback((id: string) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]));
  }, [setSelectedIds]);

  const toggleSelectAllPage = useCallback(() => {
    setSelectedIds((prev) => {
      if (rows.length === 0) {
        return prev;
      }
      const pageIds = rows.map((item) => item.id);
      const everySelected = pageIds.every((id) => prev.includes(id));
      if (everySelected) {
        return prev.filter((id) => !pageIds.includes(id));
      }
      const next = new Set(prev);
      for (const id of pageIds) {
        next.add(id);
      }
      return Array.from(next);
    });
  }, [rows, setSelectedIds]);

  const runBulkDelete = useCallback(async () => {
    if (!token || selectedIds.length === 0 || runningDelete) {
      if (selectedIds.length === 0) {
        setBulkDeleteOpen(false);
      }
      return;
    }

    setRunningDelete(true);
    try {
      const response = await bulkDeleteBackofficeOrders(token, { order_ids: selectedIds });
      const failed = response.skipped ?? [];

      if (response.deleted > 0) {
        const deletedIds = selectedIds.filter((id) => !failed.some((entry) => entry.order_id === id));
        setSelectedIds((prev) => prev.filter((id) => failed.some((entry) => entry.order_id === id)));
        onAfterDelete(deletedIds);
        await refetch();
      }

      if (failed.length === 0) {
        feedback.showSuccess(t("orders.messages.bulkDeleted", { count: response.deleted }));
      } else if (response.deleted > 0) {
        feedback.showWarning(t("orders.messages.bulkDeletePartial", { deleted: response.deleted, failed: failed.length }));
      } else {
        feedback.showApiError(new Error(failed[0]?.reason || t("orders.messages.bulkDeleteFailed")), t("orders.messages.bulkDeleteFailed"));
      }
    } catch (actionError: unknown) {
      feedback.showApiError(actionError, t("orders.messages.bulkDeleteFailed"));
    } finally {
      setRunningDelete(false);
      setBulkDeleteOpen(false);
    }
  }, [feedback, onAfterDelete, refetch, runningDelete, selectedIds, setSelectedIds, t, token]);

  useEffect(() => {
    if (!bulkActionsOpen) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (!bulkActionsRef.current) {
        return;
      }
      if (bulkActionsRef.current.contains(event.target as Node)) {
        return;
      }
      setBulkActionsOpen(false);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setBulkActionsOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [bulkActionsOpen]);

  return {
    selectedSet,
    allPageSelected,
    somePageSelected,
    runningDelete,
    bulkDeleteOpen,
    bulkActionsOpen,
    bulkActionsRef,
    setBulkDeleteOpen,
    setBulkActionsOpen,
    toggleSelected,
    toggleSelectAllPage,
    runBulkDelete,
  };
}
