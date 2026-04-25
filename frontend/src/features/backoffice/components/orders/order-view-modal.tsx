import { Ban, Check, FileX, Receipt, RefreshCw, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";

import { OrderReceiptField } from "@/features/backoffice/components/orders/order-receipt-field";
import {
  extractLabel,
  resolveDeliveryAddressParts,
  resolveDeliveryMethodLabel,
  resolveOrderPaymentMethodLabel,
  resolvePaymentMethodLabel,
  resolvePaymentStatusLabel,
  selectedActionForStatus,
  type ActionKind,
  type Translator,
} from "@/features/backoffice/components/orders/order-view-modal.helpers";
import { OrderViewValueField } from "@/features/backoffice/components/orders/order-view-value-field";
import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { formatOrderDate, resolveOrderStatusDescription } from "@/features/backoffice/lib/orders/order-formatters";
import { formatBackofficeDate } from "@/features/backoffice/lib/supplier-workspace";
import type {
  BackofficeMonobankFiscalCheck,
  BackofficeMonobankPaymentAction,
  BackofficeOrderOperational,
} from "@/features/backoffice/types/orders.types";

export function OrderViewModal({
  isOpen,
  isLoading,
  order,
  actionLoading,
  canResetToNew,
  paymentRefreshing,
  paymentRefreshDisabled,
  monobankActionLoading,
  monobankFiscalChecks,
  receiptActionLoading,
  onRunAction,
  onIssueReceipt,
  onSyncReceipt,
  onOpenReceipt,
  onRefreshPayment,
  onRunMonobankAction,
  onClose,
  t,
}: {
  isOpen: boolean;
  isLoading: boolean;
  order: BackofficeOrderOperational | null;
  actionLoading: ActionKind | null;
  canResetToNew?: boolean;
  paymentRefreshing?: boolean;
  paymentRefreshDisabled?: boolean;
  monobankActionLoading?: BackofficeMonobankPaymentAction | null;
  monobankFiscalChecks?: BackofficeMonobankFiscalCheck[];
  receiptActionLoading?: "issue" | "sync" | "open" | null;
  onRunAction: (action: ActionKind) => void;
  onIssueReceipt?: () => void;
  onSyncReceipt?: () => void;
  onOpenReceipt?: () => void;
  onRefreshPayment?: () => void;
  onRunMonobankAction?: (action: BackofficeMonobankPaymentAction, options?: { amountMinor?: number }) => void;
  onClose: () => void;
  t: Translator;
}) {
  const [selectedAction, setSelectedAction] = useState<ActionKind>("confirm");
  const [monobankAmountMinorInput, setMonobankAmountMinorInput] = useState("");

  useEffect(() => {
    if (!order) {
      return;
    }

    setSelectedAction(selectedActionForStatus(order.status, Boolean(canResetToNew)));
    setMonobankAmountMinorInput("");
  }, [canResetToNew, order]);

  const actionOptions = useMemo(() => {
    if (!order) {
      return [] as Array<{ value: ActionKind; label: string }>;
    }

    const labels: Record<ActionKind, string> = {
      confirm: t("orders.modals.view.actions.processing"),
      ready: t("orders.modals.view.actions.readyForShipment"),
      ship: t("orders.modals.view.actions.ship"),
      complete: t("orders.modals.view.actions.complete"),
      reset: t("statuses.new"),
      cancel: t("orders.modals.view.actions.cancel"),
    };
    const values: ActionKind[] = ["reset", "confirm", "ready", "ship", "complete", "cancel"];
    return values.map((value) => ({ value, label: labels[value] }));
  }, [order, t]);

  useEffect(() => {
    if (!actionOptions.length) {
      return;
    }
    if (!actionOptions.some((option) => option.value === selectedAction)) {
      setSelectedAction(actionOptions[0].value);
    }
  }, [actionOptions, selectedAction]);
  const parsedMonobankAmountMinor = useMemo(() => {
    const normalized = monobankAmountMinorInput.trim();
    if (!normalized) {
      return undefined;
    }
    if (!/^\d+$/.test(normalized)) {
      return null;
    }
    const value = Number.parseInt(normalized, 10);
    if (!Number.isFinite(value) || value <= 0) {
      return null;
    }
    return value;
  }, [monobankAmountMinorInput]);
  const deliveryAddressParts = useMemo(() => resolveDeliveryAddressParts(order, t), [order, t]);

  if (!isOpen) {
    return null;
  }

  const items = order?.items ?? [];
  const statusDescription = resolveOrderStatusDescription(order?.status || "", t);
  const orderCurrency = order?.currency || "";
  const deliveryMethodLabel = t("orders.modals.view.summary.deliveryMethod");
  const paymentMethodLabel = t("orders.modals.view.summary.paymentMethod");
  const itemsLabel = extractLabel(t("orders.modals.view.summary.items", { count: 0 }));
  const activeActionLabel = actionOptions.find((option) => option.value === selectedAction)?.label ?? t("orders.actions.refresh");
  const isMonobankPayment = (order?.payment?.provider || "").trim().toLowerCase() === "monobank";
  const isLiqPayPayment = (order?.payment?.provider || "").trim().toLowerCase() === "liqpay";

  const applyButtonStyle: CSSProperties = {
    borderColor: "#2563eb",
    backgroundColor: "#2563eb",
    color: "#ffffff",
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4">
      <button
        type="button"
        aria-label={t("orders.actions.closeModal")}
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />

      <div className="relative z-10 flex h-[94vh] w-[96vw] max-w-[1600px] flex-col overflow-hidden rounded-md border" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <header className="border-b px-4 py-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <h2 className="truncate text-base font-semibold">
                {order ? t("orders.modals.view.titleWithNumber", { number: order.order_number }) : t("orders.modals.view.title")}
              </h2>
              <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{statusDescription}</p>
            </div>
            <div className="flex items-center gap-2">
              {order ? <StatusChip status={order.status} /> : null}
              <button
                type="button"
                className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                onClick={onClose}
                aria-label={t("orders.actions.closeModal")}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-4">
          {isLoading ? (
            <p className="text-sm" style={{ color: "var(--muted)" }}>{t("loading")}</p>
          ) : !order ? (
            <p className="text-sm" style={{ color: "var(--muted)" }}>{t("orders.states.notFound")}</p>
          ) : (
            <div className="grid gap-3">
              <div className="grid gap-3 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)_minmax(0,0.92fr)_minmax(0,0.92fr)]">
                <section className="h-full rounded-md border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                  <div className="mb-2 flex items-center justify-between">
                    <p className="text-sm font-semibold">{t("orders.modals.view.items.title")}</p>
                    <p className="text-xs tabular-nums" style={{ color: "var(--muted)" }}>
                      {order.items_count}
                    </p>
                  </div>

                  <div className="space-y-2">
                    {items.length ? items.map((item) => (
                      <div key={item.id} className="rounded-md border p-2.5" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                        <div className="flex items-start gap-2">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-semibold">{item.product_name}</p>
                            <p className="mt-0.5 text-xs" style={{ color: "var(--muted)" }}>{item.product_sku}</p>
                          </div>
                        </div>

                        <div className="mt-2 grid gap-1 text-xs sm:grid-cols-3">
                          <p style={{ color: "var(--muted)" }}>{t("orders.modals.view.items.columns.qty")}: <span className="font-semibold text-[var(--text)] tabular-nums">{item.quantity}</span></p>
                          <p style={{ color: "var(--muted)" }}>{t("orders.modals.view.items.columns.price")}: <span className="font-semibold text-[var(--text)] tabular-nums">{item.unit_price} {orderCurrency}</span></p>
                          <p style={{ color: "var(--muted)" }}>{t("orders.modals.view.items.columns.total")}: <span className="font-semibold text-[var(--text)] tabular-nums">{item.line_total} {orderCurrency}</span></p>
                        </div>
                      </div>
                    )) : (
                      <div className="rounded-md border px-3 py-4 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--muted)" }}>
                        {t("orders.modals.view.items.empty")}
                      </div>
                    )}
                  </div>

                </section>

                <section className="h-full rounded-md border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-semibold">{t("orders.payment.title")}</p>
                    <div className="flex items-center gap-2">
                      {(isMonobankPayment || isLiqPayPayment) && order.payment?.page_url ? (
                        <a
                          href={order.payment.page_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex h-8 items-center justify-center rounded-md border px-3 text-sm font-medium"
                          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                        >
                          {t("orders.payment.open")}
                        </a>
                      ) : null}
                      {order.payment && onRefreshPayment ? (
                        <button
                          type="button"
                          className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
                          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                          onClick={onRefreshPayment}
                          aria-label={t("orders.payment.refreshStatus")}
                          disabled={Boolean(paymentRefreshing || paymentRefreshDisabled)}
                        >
                          <RefreshCw className="h-4 w-4 animate-spin" style={{ animationDuration: "2.2s" }} />
                        </button>
                      ) : null}
                    </div>
                  </div>

                  <div className="mt-3 grid gap-2">
                    <OrderViewValueField
                      label={t("orders.payment.method")}
                      value={resolvePaymentMethodLabel(order.payment?.method || "", t)}
                    />
                    <OrderViewValueField
                      label={t("orders.payment.status")}
                      value={resolvePaymentStatusLabel(order.payment?.status || "", t)}
                    />
                    <OrderViewValueField
                      label={t("orders.payment.amount")}
                      value={order.payment ? `${order.payment.amount} ${order.payment.currency}` : "-"}
                      bold
                    />
                    <OrderViewValueField label={t("orders.payment.lastSyncAt")} value={formatBackofficeDate(order.payment?.last_sync_at)} />
                    {(isMonobankPayment || isLiqPayPayment) ? (
                      <>
                        <OrderViewValueField label={t("orders.payment.invoiceId")} value={order.payment?.invoice_id || "-"} mono />
                        <OrderViewValueField label={t("orders.payment.reference")} value={order.payment?.reference || "-"} />
                        <OrderViewValueField label={t("orders.payment.failureReason")} value={order.payment?.failure_reason || "-"} />
                      </>
                    ) : null}
                  </div>

                  {isMonobankPayment && onRunMonobankAction ? (
                    <div className="mt-3 rounded-md border p-2.5" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                      <p className="text-xs font-semibold">{t("orders.payment.monobank.controlsTitle")}</p>

                      <label className="mt-2 block text-[11px]" style={{ color: "var(--muted)" }}>
                        {t("orders.payment.monobank.amountMinor")}
                      </label>
                      <input
                        type="text"
                        inputMode="numeric"
                        value={monobankAmountMinorInput}
                        onChange={(event) => setMonobankAmountMinorInput(event.target.value)}
                        placeholder={t("orders.payment.monobank.amountMinorHint")}
                        className="mt-1 h-9 w-full rounded-md border px-3 text-sm"
                        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                      />
                      {parsedMonobankAmountMinor === null ? (
                        <p className="mt-1 text-[11px]" style={{ color: "#b91c1c" }}>
                          {t("orders.payment.monobank.amountMinorInvalid")}
                        </p>
                      ) : null}

                      <div className="mt-2 flex items-center justify-center gap-2">
                        <BackofficeTooltip content={t("orders.payment.monobank.tooltips.finalize")} placement="top" align="center" wrapperClassName="inline-flex">
                          <button
                            type="button"
                            className="inline-flex h-9 w-9 items-center justify-center rounded-md border disabled:cursor-not-allowed disabled:opacity-60"
                            style={{ borderColor: "#111827", backgroundColor: "#111827", color: "#ffffff" }}
                            onClick={() => onRunMonobankAction("finalize", parsedMonobankAmountMinor ? { amountMinor: parsedMonobankAmountMinor } : undefined)}
                            disabled={Boolean(monobankActionLoading) || parsedMonobankAmountMinor === null}
                            aria-label={t("orders.payment.monobank.tooltips.finalize")}
                          >
                            <Check className="h-4 w-4" />
                          </button>
                        </BackofficeTooltip>
                        <BackofficeTooltip content={t("orders.payment.monobank.tooltips.cancel")} placement="top" align="center" wrapperClassName="inline-flex">
                          <button
                            type="button"
                            className="inline-flex h-9 w-9 items-center justify-center rounded-md border disabled:cursor-not-allowed disabled:opacity-60"
                            style={{ borderColor: "#dc2626", backgroundColor: "#dc2626", color: "#ffffff" }}
                            onClick={() => onRunMonobankAction("cancel", parsedMonobankAmountMinor ? { amountMinor: parsedMonobankAmountMinor } : undefined)}
                            disabled={Boolean(monobankActionLoading) || parsedMonobankAmountMinor === null}
                            aria-label={t("orders.payment.monobank.tooltips.cancel")}
                          >
                            <Ban className="h-4 w-4" />
                          </button>
                        </BackofficeTooltip>
                        <BackofficeTooltip content={t("orders.payment.monobank.tooltips.remove")} placement="top" align="center" wrapperClassName="inline-flex">
                          <button
                            type="button"
                            className="inline-flex h-9 w-9 items-center justify-center rounded-md border disabled:cursor-not-allowed disabled:opacity-60"
                            style={{ borderColor: "#f59e0b", backgroundColor: "#f59e0b", color: "#ffffff" }}
                            onClick={() => onRunMonobankAction("remove")}
                            disabled={Boolean(monobankActionLoading)}
                            aria-label={t("orders.payment.monobank.tooltips.remove")}
                          >
                            <FileX className="h-4 w-4" />
                          </button>
                        </BackofficeTooltip>
                        <BackofficeTooltip content={t("orders.payment.monobank.tooltips.fiscalChecks")} placement="top" align="center" wrapperClassName="inline-flex">
                          <button
                            type="button"
                            className="inline-flex h-9 w-9 items-center justify-center rounded-md border disabled:cursor-not-allowed disabled:opacity-60"
                            style={{ borderColor: "#d1d5db", backgroundColor: "#e5e7eb", color: "#111827" }}
                            onClick={() => onRunMonobankAction("fiscal_checks")}
                            disabled={Boolean(monobankActionLoading)}
                            aria-label={t("orders.payment.monobank.tooltips.fiscalChecks")}
                          >
                            <Receipt className="h-4 w-4" />
                          </button>
                        </BackofficeTooltip>
                      </div>

                      {Array.isArray(monobankFiscalChecks) && monobankFiscalChecks.length ? (
                        <div className="mt-2 rounded-md border p-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                          <p className="text-xs font-semibold">{t("orders.payment.monobank.fiscalChecksTitle")}</p>
                          <div className="mt-1 space-y-1.5">
                            {monobankFiscalChecks.map((check, index) => (
                              <div key={`${check.id || "check"}-${index}`} className="rounded-md border px-2 py-1.5 text-xs" style={{ borderColor: "var(--border)" }}>
                                <p><span style={{ color: "var(--muted)" }}>ID: </span>{check.id || "-"}</p>
                                <p><span style={{ color: "var(--muted)" }}>{t("orders.payment.status")}: </span>{check.status || "-"}</p>
                                <p><span style={{ color: "var(--muted)" }}>{t("orders.payment.monobank.fiscalType")}: </span>{check.type || "-"}</p>
                                <p><span style={{ color: "var(--muted)" }}>{t("orders.payment.monobank.fiscalSource")}: </span>{check.fiscalizationSource || "-"}</p>
                                {check.taxUrl ? (
                                  <a href={check.taxUrl} target="_blank" rel="noreferrer" className="underline">
                                    {t("orders.payment.monobank.taxUrl")}
                                  </a>
                                ) : null}
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </section>

                <section className="h-full rounded-md border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                  <p className="text-sm font-semibold">{t("orders.modals.view.summary.customer")}</p>

                  <div className="mt-3 grid gap-2">
                    <OrderViewValueField label={t("orders.modals.view.summary.fullName")} value={order.contact_full_name || "-"} bold />
                    <OrderViewValueField label="Email" value={order.contact_email || order.user_email || "-"} />
                    <OrderViewValueField label={t("orders.modals.view.summary.phone")} value={order.contact_phone || "-"} />
                    <OrderViewValueField label={t("orders.modals.view.summary.deliveryCity")} value={deliveryAddressParts.city} />
                    <OrderViewValueField label={t("orders.modals.view.summary.deliveryDestination")} value={deliveryAddressParts.destination} />
                  </div>
                </section>

                <section className="h-full rounded-md border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                  <p className="text-xl font-semibold tracking-tight">{order.order_number}</p>

                  <div className="mt-3">
                    <p className="mb-1.5 text-[11px]" style={{ color: "var(--muted)" }}>{t("orders.table.columns.status")}</p>
                    <div className="flex items-center gap-2">
                      <select
                        value={selectedAction}
                        onChange={(event) => setSelectedAction(event.target.value as ActionKind)}
                        className="h-9 flex-1 rounded-md border px-3 text-sm"
                        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--text)" }}
                        disabled={Boolean(actionLoading)}
                      >
                        {actionOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>

                      <BackofficeTooltip content={activeActionLabel} placement="top" align="center" wrapperClassName="inline-flex" tooltipClassName="whitespace-nowrap">
                        <button
                          type="button"
                          className="inline-flex h-9 w-9 items-center justify-center rounded-md border"
                          style={applyButtonStyle}
                          onClick={() => onRunAction(selectedAction)}
                          disabled={Boolean(actionLoading) || !actionOptions.length}
                          aria-label={activeActionLabel}
                        >
                          <RefreshCw className="h-4 w-4 animate-spin" style={{ animationDuration: "2.2s" }} />
                        </button>
                      </BackofficeTooltip>
                    </div>
                  </div>

                  <div className="mt-3 rounded-md border p-2.5" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                    <p className="flex items-center justify-between text-sm">
                      <span style={{ color: "var(--muted)" }}>{itemsLabel}</span>
                      <span className="font-semibold tabular-nums">{order.items_count}</span>
                    </p>
                    <p className="mt-1 flex items-center justify-between text-sm">
                      <span style={{ color: "var(--muted)" }}>{t("orders.table.columns.total")}</span>
                      <span className="font-semibold tabular-nums">{order.total} {orderCurrency}</span>
                    </p>
                  </div>

                  <div className="mt-3 grid gap-2">
                    <OrderViewValueField label={deliveryMethodLabel} value={resolveDeliveryMethodLabel(order.delivery_method, t)} />
                    <OrderViewValueField label={paymentMethodLabel} value={resolveOrderPaymentMethodLabel(order.payment_method, t)} />
                    <OrderViewValueField label={t("orders.table.columns.created")} value={formatOrderDate(order.placed_at)} />
                    <OrderReceiptField
                      receipt={order.receipt}
                      isLoading={receiptActionLoading ?? null}
                      onIssue={() => onIssueReceipt?.()}
                      onSync={() => onSyncReceipt?.()}
                      onOpen={() => onOpenReceipt?.()}
                      t={t}
                    />
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
