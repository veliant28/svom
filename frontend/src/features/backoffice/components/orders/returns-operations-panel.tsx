"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ListChecks } from "lucide-react";

import { getBackofficeReturnDetail, getBackofficeReturns, updateBackofficeReturnStatus } from "@/features/backoffice/api/returns-api";
import { ReturnViewModal } from "@/features/backoffice/components/orders/return-view-modal";
import { ReturnsTable } from "@/features/backoffice/components/orders/returns-table";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { ORDERS_PAGE_SIZE_OPTIONS, type OrderPageSize } from "@/features/backoffice/hooks/use-order-filters";
import { BACKOFFICE_CAPABILITIES, hasBackofficeCapability } from "@/features/backoffice/lib/capabilities";
import type { BackofficeReturnOperational } from "@/features/backoffice/types/returns.types";
import { useAuth } from "@/features/auth/hooks/use-auth";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function ReturnsOperationsPanel({
  t,
  refreshNonce = 0,
}: {
  t: Translator;
  refreshNonce?: number;
}) {
  const { token, user } = useAuth();
  const { showApiError, showSuccess } = useBackofficeFeedback();

  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<OrderPageSize>(15);
  const [selectedSet, setSelectedSet] = useState<Set<string>>(new Set());
  const [bulkActionsOpen, setBulkActionsOpen] = useState(false);
  const bulkActionsRef = useRef<HTMLDivElement | null>(null);

  const [rows, setRows] = useState<BackofficeReturnOperational[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [pagesCount, setPagesCount] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [viewOpen, setViewOpen] = useState(false);
  const [viewLoading, setViewLoading] = useState(false);
  const [viewUpdating, setViewUpdating] = useState(false);
  const [viewSavingComment, setViewSavingComment] = useState(false);
  const [viewItem, setViewItem] = useState<BackofficeReturnOperational | null>(null);

  const canRefund = hasBackofficeCapability(user, BACKOFFICE_CAPABILITIES.returnsRefund);

  const loadRows = useCallback(async () => {
    if (!token) {
      setRows([]);
      setTotalCount(0);
      setPagesCount(1);
      setIsLoading(false);
      setError(null);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const response = await getBackofficeReturns(token, { q, status, page, page_size: pageSize });
      setRows(response.results);
      setTotalCount(response.count);
      setPagesCount(Math.max(1, Math.ceil(Math.max(response.count, 1) / pageSize)));
    } catch (requestError) {
      setRows([]);
      setTotalCount(0);
      setPagesCount(1);
      setError(showApiError(requestError, t("returns.messages.loadFailed")));
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, q, showApiError, status, t, token]);

  useEffect(() => {
    void loadRows();
  }, [loadRows, refreshNonce]);

  useEffect(() => {
    setSelectedSet(new Set());
  }, [rows]);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!bulkActionsRef.current) {
        return;
      }
      if (bulkActionsRef.current.contains(event.target as Node)) {
        return;
      }
      setBulkActionsOpen(false);
    }

    document.addEventListener("mousedown", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
    };
  }, []);

  async function handleOpen(item: BackofficeReturnOperational) {
    if (!token) {
      return;
    }
    setViewOpen(true);
    setViewLoading(true);
    try {
      const detail = await getBackofficeReturnDetail(token, item.id);
      setViewItem(detail);
    } catch (requestError) {
      showApiError(requestError, t("returns.messages.detailFailed"));
      setViewOpen(false);
    } finally {
      setViewLoading(false);
    }
  }

  async function handleUpdateStatus(payload: {
    status: BackofficeReturnOperational["status"];
    admin_comment?: string;
    rejection_reason?: string;
    approved_items?: Array<{ item_id: string; quantity_approved: number }>;
  }) {
    if (!token || !viewItem) {
      return;
    }
    setViewUpdating(true);
    try {
      const updated = await updateBackofficeReturnStatus(token, viewItem.id, payload);
      setViewItem(updated);
      setRows((current) => current.map((row) => (row.id === updated.id ? { ...row, ...updated } : row)));
      const statusMessageMap: Record<string, string> = {
        approved: t("returns.messages.approved"),
        rejected: t("returns.messages.rejected"),
        accepted: t("returns.messages.accepted"),
        refunded: t("returns.messages.refund"),
        cancelled: t("returns.messages.cancelled"),
      };
      showSuccess(statusMessageMap[payload.status] || t("returns.messages.statusUpdated"));
      void loadRows();
    } catch (requestError) {
      showApiError(requestError, t("returns.messages.statusUpdateFailed"));
    } finally {
      setViewUpdating(false);
    }
  }

  async function handleSaveAdminComment(nextComment: string) {
    if (!token || !viewItem || viewSavingComment) {
      return;
    }
    setViewSavingComment(true);
    try {
      const updated = await updateBackofficeReturnStatus(token, viewItem.id, {
        status: viewItem.status,
        admin_comment: nextComment,
      });
      setViewItem(updated);
      setRows((current) => current.map((row) => (row.id === updated.id ? { ...row, ...updated } : row)));
      showSuccess(t("returns.messages.adminCommentSaved"));
    } catch (requestError) {
      showApiError(requestError, t("returns.messages.statusUpdateFailed"));
    } finally {
      setViewSavingComment(false);
    }
  }

  const statusOptions = useMemo(
    () => [
      { value: "", label: t("returns.filters.allStatuses") },
      { value: "new", label: t("statuses.new") },
      { value: "approved", label: t("statuses.approved") },
      { value: "rejected", label: t("statuses.rejected") },
      { value: "awaiting_ttn", label: t("statuses.no_ttn") },
      { value: "in_transit", label: t("statuses.in_transit") },
      { value: "accepted", label: t("statuses.accepted") },
      { value: "refund", label: t("statuses.refund") },
      { value: "cancelled", label: t("statuses.cancelled") },
    ],
    [t],
  );

  const rowIds = useMemo(() => rows.map((row) => row.id), [rows]);
  const allPageSelected = rowIds.length > 0 && rowIds.every((id) => selectedSet.has(id));
  const somePageSelected = rowIds.some((id) => selectedSet.has(id)) && !allPageSelected;

  function toggleSelected(id: string) {
    setSelectedSet((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function toggleSelectAllPage() {
    setSelectedSet((current) => {
      const next = new Set(current);
      if (allPageSelected) {
        rowIds.forEach((id) => next.delete(id));
      } else {
        rowIds.forEach((id) => next.add(id));
      }
      return next;
    });
  }

  function clearSelection() {
    setSelectedSet(new Set());
    setBulkActionsOpen(false);
  }

  return (
    <section>
      <section className="mb-3 flex items-center gap-2">
        <div ref={bulkActionsRef} className="relative shrink-0">
          <button
            type="button"
            aria-label={t("returns.actions.bulkActions")}
            aria-haspopup="menu"
            aria-expanded={bulkActionsOpen}
            className="inline-flex h-10 w-10 items-center justify-center rounded-md border"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            onClick={() => setBulkActionsOpen((prev) => !prev)}
          >
            <ListChecks size={16} />
          </button>
          {bulkActionsOpen ? (
            <div
              role="menu"
              className="absolute left-0 top-full z-30 mt-1 min-w-[260px] rounded-lg border p-1.5 shadow-xl"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            >
              <p className="px-3 pb-1 text-xs" style={{ color: "var(--muted)" }}>
                {t("returns.bulk.selected", { count: selectedSet.size })}
              </p>
              <button
                type="button"
                role="menuitem"
                disabled={selectedSet.size <= 0}
                className="flex h-10 w-full items-center rounded-md px-3 text-left text-sm font-normal leading-5 disabled:opacity-50"
                onClick={clearSelection}
              >
                {t("returns.actions.clearSelection")}
              </button>
            </div>
          ) : null}
        </div>
        <div className="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto px-1 py-1">
          <input
            value={q}
            onChange={(event) => {
              setQ(event.target.value);
              setPage(1);
            }}
            placeholder={t("returns.filters.search")}
            className="h-10 w-[220px] xl:w-[280px] rounded-md border px-3 text-sm shrink-0"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          />

          <select
            value={String(pageSize)}
            onChange={(event) => {
              setPageSize(Number(event.target.value) as OrderPageSize);
              setPage(1);
            }}
            className="h-10 rounded-md border px-3 text-sm shrink-0"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            {ORDERS_PAGE_SIZE_OPTIONS.map((value) => (
              <option key={value} value={value}>{`${t("orders.pagination.perPage")}: ${value}`}</option>
            ))}
          </select>

          <select
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
            className="h-10 w-[132px] rounded-md border px-3 text-sm shrink-0"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
          >
            {statusOptions.map((option) => (
              <option key={option.value || "all"} value={option.value}>{option.label}</option>
            ))}
          </select>
        </div>
      </section>

      <ReturnsTable
        t={t}
        rows={rows}
        isLoading={isLoading}
        error={error}
        page={page}
        pagesCount={pagesCount}
        totalCount={totalCount}
        selectedSet={selectedSet}
        allPageSelected={allPageSelected}
        somePageSelected={somePageSelected}
        onToggleSelectAllPage={toggleSelectAllPage}
        onToggleSelected={toggleSelected}
        onOpen={(item) => {
          void handleOpen(item);
        }}
        onPageChange={setPage}
      />

      <ReturnViewModal
        isOpen={viewOpen}
        item={viewItem}
        isLoading={viewLoading}
        isUpdating={viewUpdating}
        isSavingComment={viewSavingComment}
        canRefund={canRefund}
        onUpdateStatus={(payload) => {
          void handleUpdateStatus(payload);
        }}
        onSaveAdminComment={(nextComment) => {
          void handleSaveAdminComment(nextComment);
        }}
        onClose={() => {
          setViewOpen(false);
          setViewItem(null);
        }}
        t={t}
      />
    </section>
  );
}
