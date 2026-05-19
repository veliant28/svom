"use client";

import { RefreshCw, RotateCcw, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";

import { OrderModalStaffActor } from "@/features/backoffice/components/orders/order-modal-staff-actor";
import { OrderViewValueField } from "@/features/backoffice/components/orders/order-view-value-field";
import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import { ReturnStatusChip } from "@/features/backoffice/components/widgets/return-status-chip";
import { formatBackofficeDate } from "@/features/backoffice/lib/supplier-workspace";
import type { BackofficeReturnOperational } from "@/features/backoffice/types/returns.types";
import { formatFooterPhoneDisplay } from "@/shared/lib/footer-phone";

type Translator = (key: string, values?: Record<string, string | number>) => string;

const STATUS_ORDER: Array<{ value: BackofficeReturnOperational["status"]; key: string }> = [
  { value: "approved", key: "approve" },
  { value: "rejected", key: "reject" },
  { value: "received", key: "received" },
  { value: "accepted", key: "accepted" },
  { value: "refund_processing", key: "refundProcessing" },
  { value: "refunded", key: "refunded" },
];

const TRANSITIONS: Record<string, string[]> = {
  new: ["approved", "rejected", "cancelled"],
  approved: ["awaiting_ttn", "cancelled"],
  awaiting_ttn: ["cancelled"],
  in_transit: ["received", "cancelled"],
  received: ["accepted"],
  accepted: ["refund_processing"],
  refund_processing: ["refunded"],
};

export function ReturnViewModal({
  isOpen,
  item,
  isLoading,
  isUpdating,
  canRefund,
  onUpdateStatus,
  onClose,
  t,
}: {
  isOpen: boolean;
  item: BackofficeReturnOperational | null;
  isLoading: boolean;
  isUpdating: boolean;
  canRefund: boolean;
  onUpdateStatus: (payload: {
    status: BackofficeReturnOperational["status"];
    admin_comment?: string;
    rejection_reason?: string;
    approved_items?: Array<{ item_id: string; quantity_approved: number }>;
  }) => void;
  onClose: () => void;
  t: Translator;
}) {
  const [selectedStatus, setSelectedStatus] = useState<BackofficeReturnOperational["status"]>("approved");
  const [adminComment, setAdminComment] = useState("");
  const [rejectionReason, setRejectionReason] = useState("");
  const [excludedItemIds, setExcludedItemIds] = useState<Set<string>>(new Set());

  const availableStatuses = useMemo(() => {
    if (!item) {
      return [] as typeof STATUS_ORDER;
    }
    const allowed = new Set((TRANSITIONS[item.status] || []) as BackofficeReturnOperational["status"][]);
    return STATUS_ORDER.filter((status) => {
      if (!allowed.has(status.value)) {
        return false;
      }
      if (status.value === "refunded" && !canRefund) {
        return false;
      }
      return true;
    });
  }, [canRefund, item]);

  useEffect(() => {
    if (!availableStatuses.length) {
      return;
    }
    setSelectedStatus(availableStatuses[0].value);
  }, [availableStatuses]);

  useEffect(() => {
    setAdminComment("");
    setRejectionReason("");
  }, [item?.id]);

  useEffect(() => {
    if (!item) {
      setExcludedItemIds(new Set());
      return;
    }
    if (item.status === "new") {
      setExcludedItemIds(new Set());
      return;
    }
    const inactiveIds = (item.items || [])
      .filter((row) => Number(row.quantity_requested || 0) > 0 && Number(row.quantity_approved || 0) <= 0)
      .map((row) => row.id);
    setExcludedItemIds(new Set(inactiveIds));
  }, [item]);

  if (!isOpen) {
    return null;
  }

  const rows = item?.items ?? [];
  const canEditApprovalItems = Boolean(item && item.status === "new");
  const rowStates = rows.map((row) => {
    const requestedQty = Math.max(0, Number(row.quantity_requested || 0));
    const approvedQtyStored = Math.max(0, Number(row.quantity_approved || 0));
    const isInactive = canEditApprovalItems
      ? excludedItemIds.has(row.id)
      : requestedQty > 0 && approvedQtyStored <= 0;
    const approvedQty = canEditApprovalItems
      ? (isInactive ? 0 : requestedQty)
      : approvedQtyStored;
    return {
      row,
      isInactive,
      approvedQty,
    };
  });
  const approvedRowStates = rowStates.filter((entry) => entry.approvedQty > 0);
  const positionsCount = approvedRowStates.length;
  const quantityCount = approvedRowStates.reduce((sum, entry) => sum + Math.max(0, Number(entry.approvedQty || 0)), 0);
  const totalRefundAmount = (approvedRowStates.reduce((sum, entry) => {
    const value = Number(String(entry.row.refund_amount || "").replace(",", "."));
    if (!Number.isFinite(value)) {
      return sum;
    }
    return sum + value;
  }, 0)).toFixed(2);
  const selectedActionMeta = availableStatuses.find((status) => status.value === selectedStatus);
  const activeActionLabel = selectedActionMeta ? t(`returns.statusActions.${selectedActionMeta.key}`) : t("returns.actions.apply");
  const applyButtonStyle: CSSProperties = {
    borderColor: "#2563eb",
    backgroundColor: "#2563eb",
    color: "#ffffff",
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4">
      <button
        type="button"
        aria-label={t("returns.actions.close")}
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />

      <div className="relative z-10 flex h-auto max-h-[94vh] w-[96vw] max-w-[872px] flex-col overflow-hidden rounded-md border" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <header className="border-b px-4 py-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="truncate text-base font-semibold">{item?.return_number || t("returns.title")}</h2>
                {item ? <ReturnStatusChip status={item.status} /> : null}
              </div>
              {item ? (
                <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                  {t("returns.labels.order", { value: item.order_number })} · {formatBackofficeDate(item.created_at)}
                </p>
              ) : null}
            </div>
            <div className="flex items-start gap-2">
              <OrderModalStaffActor actor={item?.last_actor ?? null} />
              <button
                type="button"
                className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                onClick={onClose}
                aria-label={t("returns.actions.close")}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-4">
          {isLoading ? (
            <p className="text-sm" style={{ color: "var(--muted)" }}>{t("loading")}</p>
          ) : !item ? (
            <p className="text-sm" style={{ color: "var(--muted)" }}>{t("returns.states.empty")}</p>
          ) : (
            <div className="grid gap-3">
              <div className="grid gap-3 xl:grid-cols-[488px_340px]">
                <section className="h-full rounded-md border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                  <div className="mb-2 flex items-center justify-between">
                    <p className="text-sm font-semibold">{t("returns.labels.items")}</p>
                    <p className="text-xs tabular-nums" style={{ color: "var(--muted)" }}>{rows.length}</p>
                  </div>

                  <div className="space-y-2">
                    {rows.length ? rows.map((row) => (
                      <div key={row.id} className="rounded-md border p-2.5" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                        {(() => {
                          const state = rowStates.find((entry) => entry.row.id === row.id);
                          const isInactive = Boolean(state?.isInactive);
                          const approvedQty = state?.approvedQty ?? Number(row.quantity_approved || 0);
                          const actionLabel = isInactive ? t("returns.actions.restoreApprovalItem") : t("returns.actions.excludeApprovalItem");
                          return (
                            <div className={isInactive ? "opacity-45" : ""}>
                              <div className="flex items-start justify-between gap-2">
                                <div className="min-w-0">
                                  <p className="truncate text-sm font-semibold">{row.product_display_name || row.product_name_snapshot || "-"}</p>
                                  <p className="mt-0.5 text-xs" style={{ color: "var(--muted)" }}>{row.product_svom_sku || row.product_sku_snapshot || "-"}</p>
                                </div>
                                {canEditApprovalItems ? (
                                  <BackofficeTooltip content={actionLabel} placement="top" align="center" wrapperClassName="inline-flex shrink-0" tooltipClassName="whitespace-nowrap">
                                    <button
                                      type="button"
                                      className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
                                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                                      onClick={() => {
                                        setExcludedItemIds((current) => {
                                          const next = new Set(current);
                                          if (next.has(row.id)) {
                                            next.delete(row.id);
                                          } else {
                                            next.add(row.id);
                                          }
                                          return next;
                                        });
                                      }}
                                      aria-label={actionLabel}
                                    >
                                      {isInactive ? <RotateCcw className="h-4 w-4" /> : <Trash2 className="h-4 w-4" />}
                                    </button>
                                  </BackofficeTooltip>
                                ) : null}
                              </div>

                              <div className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
                                <div className="flex items-center justify-between gap-3">
                                  <span>{t("returns.labels.qty", { requested: row.quantity_requested, approved: canEditApprovalItems ? 0 : approvedQty })}</span>
                                  <span>
                                    {t("returns.labels.quantity")}: <span className="font-semibold text-[var(--text)] tabular-nums">{canEditApprovalItems ? row.quantity_requested : approvedQty}</span>
                                  </span>
                                  <span className="text-right">
                                    {t("returns.labels.amount")}: <span className="font-semibold text-[var(--text)] tabular-nums">{isInactive ? "0.00" : row.refund_amount}</span>
                                  </span>
                                </div>
                              </div>
                            </div>
                          );
                        })()}
                      </div>
                    )) : (
                      <div className="rounded-md border px-3 py-4 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--muted)" }}>
                        {t("returns.states.empty")}
                      </div>
                    )}
                  </div>
                </section>

                <section className="h-full rounded-md border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                  <p className="text-xl font-semibold tracking-tight">{item.return_number}</p>

                  <div className="mt-3">
                    <p className="mb-1.5 text-[11px]" style={{ color: "var(--muted)" }}>{t("returns.table.columns.status")}</p>
                    {availableStatuses.length ? (
                      <div className="flex items-center gap-2">
                        <select
                          value={selectedStatus}
                          onChange={(event) => setSelectedStatus(event.target.value as BackofficeReturnOperational["status"])}
                          className="h-9 flex-1 rounded-md border px-3 text-sm"
                          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--text)" }}
                          disabled={isUpdating}
                        >
                          {availableStatuses.map((status) => (
                            <option key={status.value} value={status.value}>
                              {t(`returns.statusActions.${status.key}`)}
                            </option>
                          ))}
                        </select>

                        <BackofficeTooltip content={activeActionLabel} placement="top" align="center" wrapperClassName="inline-flex" tooltipClassName="whitespace-nowrap">
                          <button
                            type="button"
                            className="inline-flex h-9 w-9 items-center justify-center rounded-md border"
                            style={applyButtonStyle}
                            onClick={() => {
                              onUpdateStatus({
                                status: selectedStatus,
                                admin_comment: adminComment.trim() || undefined,
                                rejection_reason: selectedStatus === "rejected" ? rejectionReason.trim() : undefined,
                                approved_items: canEditApprovalItems && selectedStatus === "approved"
                                  ? rowStates.map((entry) => ({
                                    item_id: entry.row.id,
                                    quantity_approved: entry.approvedQty,
                                  }))
                                  : undefined,
                              });
                            }}
                            disabled={isUpdating || (selectedStatus === "rejected" && !rejectionReason.trim()) || (canEditApprovalItems && selectedStatus === "approved" && positionsCount <= 0)}
                            aria-label={activeActionLabel}
                          >
                            <RefreshCw className={`h-4 w-4 ${isUpdating ? "animate-spin" : ""}`} style={{ animationDuration: "2.2s" }} />
                          </button>
                        </BackofficeTooltip>
                      </div>
                    ) : (
                      <p className="text-xs" style={{ color: "var(--muted)" }}>{t("returns.actions.noTransitions")}</p>
                    )}
                  </div>

                  <div className="mt-3 rounded-md border p-2.5" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                    <p className="mt-1 flex items-center justify-between text-sm">
                      <span style={{ color: "var(--muted)" }}>{t("returns.labels.positions")}</span>
                      <span className="font-semibold tabular-nums">{positionsCount}</span>
                    </p>
                    <p className="mt-1 flex items-center justify-between text-sm">
                      <span style={{ color: "var(--muted)" }}>{t("returns.labels.quantity")}</span>
                      <span className="font-semibold tabular-nums">{quantityCount}</span>
                    </p>
                    <p className="mt-1 flex items-center justify-between text-sm">
                      <span style={{ color: "var(--muted)" }}>{t("returns.labels.total")}</span>
                      <span className="font-semibold tabular-nums">{totalRefundAmount} UAH</span>
                    </p>
                  </div>

                  <div className="mt-3 grid gap-2">
                    <OrderViewValueField label={t("returns.labels.customer")} value={item.customer_name || "-"} bold />
                    <OrderViewValueField label={t("returns.labels.email")} value={item.customer_email || "-"} />
                    <OrderViewValueField label={t("returns.labels.phone")} value={formatFooterPhoneDisplay(item.customer_phone || "") || "-"} />
                    <OrderViewValueField label={t("returns.labels.tracking")} value={item.tracking_number || t("returns.labels.noTtn")} mono />
                  </div>

                  <div className="mt-3 rounded-md border p-2.5" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                    <p className="text-[11px]" style={{ color: "var(--muted)" }}>{t("returns.labels.customerReason")}</p>
                    <p className="mt-1 text-sm font-medium text-[var(--text)]">{item.reason_comment || "-"}</p>
                    {item.rejection_reason ? (
                      <>
                        <p className="mt-3 text-xs font-semibold">{t("returns.labels.rejectionReason")}</p>
                        <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>{item.rejection_reason}</p>
                      </>
                    ) : null}
                    {item.admin_comment ? (
                      <>
                        <p className="mt-3 text-xs font-semibold">{t("returns.actions.adminComment")}</p>
                        <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>{item.admin_comment}</p>
                      </>
                    ) : null}
                  </div>

                  <div className="mt-3 grid gap-2">
                    <input
                      type="text"
                      value={adminComment}
                      onChange={(event) => setAdminComment(event.target.value)}
                      placeholder={t("returns.actions.adminComment")}
                      className="h-9 rounded-md border px-3 text-sm"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                    />

                    {selectedStatus === "rejected" ? (
                      <input
                        type="text"
                        value={rejectionReason}
                        onChange={(event) => setRejectionReason(event.target.value)}
                        placeholder={t("returns.actions.rejectionReason")}
                        className="h-9 rounded-md border px-3 text-sm"
                        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                      />
                    ) : null}
                  </div>
                </section>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
