import { RefreshCw, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";

import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { formatOrderDate, resolveOrderStatusDescription } from "@/features/backoffice/lib/orders/order-formatters";
import type { BackofficeOrderOperational } from "@/features/backoffice/types/orders.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

type ActionKind = "confirm" | "awaiting" | "reserve" | "ready" | "cancel";

function ValueField({
  label,
  value,
  mono = false,
  bold = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
  bold?: boolean;
}) {
  return (
    <div className="rounded-md border px-3 py-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
      <p className="text-[11px]" style={{ color: "var(--muted)" }}>{label}</p>
      <p className={`mt-1 text-sm ${mono ? "font-mono" : ""} ${bold ? "font-semibold" : "font-medium"} text-[var(--text)]`}>
        {value || "-"}
      </p>
    </div>
  );
}

function extractLabel(sentence: string): string {
  const [label] = sentence.split(":");
  return label.trim();
}

function humanizeCode(value: string): string {
  if (!value) {
    return "-";
  }

  return value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .trim();
}

function nextActionForStatus(status: string): ActionKind {
  const normalized = status.trim().toLowerCase();

  if (normalized === "new") {
    return "confirm";
  }
  if (normalized === "confirmed") {
    return "awaiting";
  }
  if (normalized === "awaiting_procurement") {
    return "reserve";
  }
  if (normalized === "reserved" || normalized === "partially_reserved") {
    return "ready";
  }
  if (normalized === "cancelled") {
    return "cancel";
  }

  return "ready";
}

export function OrderViewModal({
  isOpen,
  isLoading,
  order,
  actionLoading,
  onRunAction,
  onClose,
  t,
}: {
  isOpen: boolean;
  isLoading: boolean;
  order: BackofficeOrderOperational | null;
  actionLoading: ActionKind | null;
  onRunAction: (action: ActionKind) => void;
  onClose: () => void;
  t: Translator;
}) {
  const [selectedAction, setSelectedAction] = useState<ActionKind>("confirm");

  useEffect(() => {
    if (!order) {
      return;
    }

    setSelectedAction(nextActionForStatus(order.status));
  }, [order]);

  const actionOptions = useMemo(() => ([
    { value: "confirm" as const, label: t("orders.modals.view.actions.confirm") },
    { value: "awaiting" as const, label: t("orders.modals.view.actions.awaiting") },
    { value: "reserve" as const, label: t("orders.modals.view.actions.reserve") },
    { value: "ready" as const, label: t("orders.modals.view.actions.ready") },
    { value: "cancel" as const, label: t("orders.modals.view.actions.cancel") },
  ]), [t]);

  if (!isOpen) {
    return null;
  }

  const items = order?.items ?? [];
  const statusDescription = resolveOrderStatusDescription(order?.status || "", t);
  const orderCurrency = order?.currency || "";
  const deliveryLabel = extractLabel(t("orders.modals.view.summary.delivery", { value: "" }));
  const itemsLabel = extractLabel(t("orders.modals.view.summary.items", { count: 0 }));
  const customerCommentLabel = extractLabel(t("orders.modals.view.serviceInfo.customerComment", { value: "" }));
  const internalNotesLabel = extractLabel(t("orders.modals.view.serviceInfo.internalNotes", { value: "" }));
  const operatorNotesLabel = extractLabel(t("orders.modals.view.serviceInfo.operatorNotes", { value: "" }));
  const activeActionLabel = actionOptions.find((option) => option.value === selectedAction)?.label ?? t("orders.actions.refresh");

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
                <section className="rounded-md border p-3 xl:row-span-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                  <div className="mb-2 flex items-center justify-between">
                    <p className="text-sm font-semibold">{t("orders.modals.view.items.title")}</p>
                    <p className="text-xs tabular-nums" style={{ color: "var(--muted)" }}>
                      {order.items_count}
                    </p>
                  </div>

                  <div className="space-y-2">
                    {items.length ? items.map((item) => (
                      <div key={item.id} className="rounded-md border p-2.5" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-semibold">{item.product_name}</p>
                            <p className="mt-0.5 text-xs" style={{ color: "var(--muted)" }}>{item.product_sku}</p>
                          </div>
                          <StatusChip status={item.procurement_status} />
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

                  <div className="mt-3 rounded-md border px-3 py-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                    <p className="text-[11px]" style={{ color: "var(--muted)" }}>{t("orders.modals.view.summary.total")}</p>
                    <p className="mt-1 text-base font-semibold tabular-nums">{order.total} {orderCurrency}</p>
                  </div>
                </section>

                <section className="rounded-md border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                  <p className="text-sm font-semibold">{t("orders.modals.view.summary.meta")}</p>
                  <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{statusDescription}</p>

                  <div className="mt-3 grid gap-2">
                    <ValueField label={t("orderDetail.summary.status")} value={order.status || "-"} />
                    <ValueField label={t("orders.table.columns.created")} value={formatOrderDate(order.placed_at)} />
                    <ValueField label={deliveryLabel} value={humanizeCode(order.delivery_method)} />
                    <ValueField label={t("orders.table.columns.total")} value={`${order.total} ${orderCurrency}`} bold />
                  </div>
                </section>

                <section className="rounded-md border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                  <p className="text-sm font-semibold">{t("orders.modals.view.summary.customer")}</p>

                  <div className="mt-3 grid gap-2">
                    <ValueField label={t("orders.table.columns.client")} value={order.contact_full_name || "-"} bold />
                    <ValueField label="Email" value={order.contact_email || order.user_email || "-"} />
                    <ValueField label="Phone" value={order.contact_phone || "-"} />
                  </div>
                </section>

                <section className="rounded-md border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                  <p className="text-xl font-semibold tracking-tight">{order.order_number}</p>

                  <div className="mt-3">
                    <p className="mb-1.5 text-[11px]" style={{ color: "var(--muted)" }}>{t("orders.table.columns.status")}</p>
                    <div className="flex items-center gap-2">
                      <select
                        value={selectedAction}
                        onChange={(event) => setSelectedAction(event.target.value as ActionKind)}
                        className="h-10 flex-1 rounded-md border px-3 text-sm"
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
                          className="inline-flex h-10 w-10 items-center justify-center rounded-md border"
                          style={applyButtonStyle}
                          onClick={() => onRunAction(selectedAction)}
                          disabled={Boolean(actionLoading)}
                          aria-label={activeActionLabel}
                        >
                          <RefreshCw className={`h-5 w-5 ${actionLoading ? "animate-spin" : ""}`} />
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
                    <ValueField label={deliveryLabel} value={humanizeCode(order.delivery_method)} />
                    <ValueField label="Payment" value={humanizeCode(order.payment_method)} />
                    <ValueField label={t("orders.table.columns.created")} value={formatOrderDate(order.placed_at)} />
                  </div>
                </section>

                <section className="rounded-md border p-3 xl:col-span-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
                  <p className="text-sm font-semibold">{t("orders.modals.view.serviceInfo.title")}</p>
                  <div className="mt-2 grid gap-2 md:grid-cols-3">
                    <ValueField label={customerCommentLabel} value={order.customer_comment || "-"} />
                    <ValueField label={internalNotesLabel} value={order.internal_notes || "-"} />
                    <ValueField label={operatorNotesLabel} value={order.operator_notes || "-"} />
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
