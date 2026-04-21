import { Ban, Check, FileX, Receipt, RefreshCw, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";

import { BackofficeTooltip } from "@/features/backoffice/components/widgets/backoffice-tooltip";
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import { formatOrderDate, resolveOrderStatusDescription } from "@/features/backoffice/lib/orders/order-formatters";
import { formatBackofficeDate } from "@/features/backoffice/lib/supplier-workspace";
import type {
  BackofficeMonobankFiscalCheck,
  BackofficeMonobankPaymentAction,
  BackofficeOrderOperational,
} from "@/features/backoffice/types/orders.types";

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

function resolvePaymentMethodLabel(value: string, t: Translator): string {
  const normalized = value.trim().toLowerCase();
  if (!normalized) {
    return "-";
  }
  if (normalized === "cash_on_delivery") {
    return t("orders.payment.values.methods.cash_on_delivery");
  }
  if (normalized === "monobank") {
    return t("orders.payment.values.methods.monobank");
  }
  if (normalized === "card_placeholder") {
    return t("orders.payment.values.methods.card_placeholder");
  }
  return humanizeCode(value);
}

function resolvePaymentStatusLabel(value: string, t: Translator): string {
  const normalized = value.trim().toLowerCase();
  if (!normalized) {
    return "-";
  }
  if (normalized === "pending") {
    return t("orders.payment.values.statuses.pending");
  }
  if (normalized === "processing") {
    return t("orders.payment.values.statuses.processing");
  }
  if (normalized === "created") {
    return t("orders.payment.values.statuses.created");
  }
  if (normalized === "success") {
    return t("orders.payment.values.statuses.success");
  }
  if (normalized === "paid") {
    return t("orders.payment.values.statuses.paid");
  }
  if (normalized === "failed") {
    return t("orders.payment.values.statuses.failed");
  }
  if (normalized === "expired") {
    return t("orders.payment.values.statuses.expired");
  }
  if (normalized === "cancelled" || normalized === "canceled") {
    return t("orders.payment.values.statuses.cancelled");
  }
  return humanizeCode(value);
}

function resolveDeliveryMethodLabel(value: string, t: Translator): string {
  const normalized = value.trim().toLowerCase();
  if (!normalized) {
    return "-";
  }
  if (normalized === "pickup") {
    return t("orders.modals.view.summary.values.deliveryMethods.pickup");
  }
  if (normalized === "courier") {
    return t("orders.modals.view.summary.values.deliveryMethods.courier");
  }
  if (normalized === "nova_poshta") {
    return t("orders.modals.view.summary.values.deliveryMethods.nova_poshta");
  }
  return humanizeCode(value);
}

function resolveOrderPaymentMethodLabel(value: string, t: Translator): string {
  const normalized = value.trim().toLowerCase();
  if (!normalized) {
    return "-";
  }
  if (normalized === "cash_on_delivery") {
    return t("orders.payment.values.methods.cash_on_delivery");
  }
  if (normalized === "monobank") {
    return t("orders.payment.values.methods.monobank");
  }
  if (normalized === "card_placeholder") {
    return t("orders.payment.values.methods.card_placeholder");
  }
  return humanizeCode(value);
}

function looksLikeRegionToken(value: string): boolean {
  const normalized = value.trim().toLowerCase();
  if (!normalized) {
    return false;
  }

  if (normalized.includes("область")) {
    return true;
  }

  return (
    normalized.endsWith("обл")
    || normalized.endsWith("обл.")
    || normalized.endsWith("ская")
    || normalized.endsWith("ська")
    || normalized.endsWith("ский")
    || normalized.endsWith("ський")
  );
}

function formatCityWithRegion(city: string, region: string): string {
  const normalizedCity = city.trim();
  const normalizedRegion = region.trim();
  if (!normalizedCity && !normalizedRegion) {
    return "";
  }
  if (!normalizedRegion) {
    return normalizedCity;
  }
  if (!normalizedCity) {
    return normalizedRegion;
  }
  if (/^(г\.|м\.)\s*/i.test(normalizedCity)) {
    return `${normalizedCity}, ${normalizedRegion}`;
  }
  return `г. ${normalizedCity}, ${normalizedRegion}`;
}

function splitDeliveryAddress(rawValue: string): { city: string; destination: string; region: string } {
  const raw = rawValue.trim();
  if (!raw) {
    return { city: "", destination: "", region: "" };
  }

  const parts = raw
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
  if (!parts.length) {
    return { city: "", destination: "", region: "" };
  }

  // Common NP patterns:
  // 1) region, city, destination...
  // 2) city, region, destination...
  if (parts.length >= 3) {
    if (looksLikeRegionToken(parts[0])) {
      return {
        city: parts[1] || "",
        destination: parts.slice(2).join(", ").trim(),
        region: parts[0] || "",
      };
    }
    if (looksLikeRegionToken(parts[1])) {
      return {
        city: parts[0] || "",
        destination: parts.slice(2).join(", ").trim(),
        region: parts[1] || "",
      };
    }
  }

  let cityIndex = 0;
  let destinationStartIndex = 1;
  if (parts.length > 1 && looksLikeRegionToken(parts[0])) {
    cityIndex = 1;
    destinationStartIndex = 2;
  }

  return {
    city: parts[cityIndex] || "",
    destination: parts.slice(destinationStartIndex).join(", ").trim(),
    region: parts.length > 1 && looksLikeRegionToken(parts[0]) ? parts[0] : "",
  };
}

function normalizeDeliveryDestination(rawDestination: string, city: string): string {
  const raw = rawDestination.trim();
  if (!raw) {
    return "";
  }

  const parts = raw
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
  if (!parts.length) {
    return "";
  }

  const normalizedCity = city.trim().toLowerCase();
  const normalizedCityWithoutPrefix = normalizedCity.replace(/^(г\.|м\.)\s*/i, "").trim();
  // Drop repeated city/region tokens in any order at the beginning.
  while (parts.length) {
    const head = parts[0].toLowerCase();
    const isRegionHead = looksLikeRegionToken(parts[0]);
    const isCityHead =
      (normalizedCity && head === normalizedCity)
      || (normalizedCityWithoutPrefix && head === normalizedCityWithoutPrefix);
    if (!isRegionHead && !isCityHead) {
      break;
    }
    parts.shift();
  }

  return parts.join(", ").trim();
}

function looksLikeNovaPoshtaPointToken(value: string): boolean {
  const normalized = value.trim().toLowerCase();
  return /(відділен|отделен|поштомат|почтомат|постомат|адрес|адреса|address)/i.test(normalized);
}

function normalizeCityCandidates(value: string): string[] {
  const raw = value.trim().toLowerCase();
  if (!raw) {
    return [];
  }
  const head = raw.split(",")[0]?.trim() || "";
  const withoutPrefix = head.replace(/^(г\.|м\.)\s*/i, "").trim();
  return [head, withoutPrefix].filter(Boolean);
}

function formatNovaPoshtaDestination(rawDestination: string, city: string, t: Translator): string {
  const normalized = rawDestination.trim();
  if (!normalized) {
    return "";
  }

  const parts = normalized
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
  if (!parts.length) {
    return "";
  }

  const cityCandidates = normalizeCityCandidates(city);
  let pointToken = "";
  if (looksLikeNovaPoshtaPointToken(parts[0])) {
    pointToken = parts.shift() || "";
  }

  while (parts.length && looksLikeRegionToken(parts[0])) {
    parts.shift();
  }
  while (parts.length && cityCandidates.includes(parts[0].toLowerCase())) {
    parts.shift();
  }

  if (!pointToken && parts.length && looksLikeNovaPoshtaPointToken(parts[0])) {
    pointToken = parts.shift() || "";
  }

  const tail = parts.join(", ").trim();
  const warehouseLabel = t("orders.modals.waybill.delivery.warehouse");
  const resolvedPointToken = pointToken || warehouseLabel;
  return [resolvedPointToken, tail].filter(Boolean).join(", ");
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
  paymentRefreshing,
  paymentRefreshDisabled,
  monobankActionLoading,
  monobankFiscalChecks,
  onRunAction,
  onRefreshPayment,
  onRunMonobankAction,
  onClose,
  t,
}: {
  isOpen: boolean;
  isLoading: boolean;
  order: BackofficeOrderOperational | null;
  actionLoading: ActionKind | null;
  paymentRefreshing?: boolean;
  paymentRefreshDisabled?: boolean;
  monobankActionLoading?: BackofficeMonobankPaymentAction | null;
  monobankFiscalChecks?: BackofficeMonobankFiscalCheck[];
  onRunAction: (action: ActionKind) => void;
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

    setSelectedAction(nextActionForStatus(order.status));
    setMonobankAmountMinorInput("");
  }, [order]);

  const actionOptions = useMemo(() => ([
    { value: "confirm" as const, label: t("orders.modals.view.actions.confirm") },
    { value: "awaiting" as const, label: t("orders.modals.view.actions.awaiting") },
    { value: "reserve" as const, label: t("orders.modals.view.actions.reserve") },
    { value: "ready" as const, label: t("orders.modals.view.actions.ready") },
    { value: "cancel" as const, label: t("orders.modals.view.actions.cancel") },
  ]), [t]);
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
  const deliveryAddressParts = useMemo(() => {
    const deliveryMethod = (order?.delivery_method || "").trim().toLowerCase();
    if (deliveryMethod === "pickup") {
      return {
        city: "",
        destination: "",
      };
    }

    const cityLabel = (order?.delivery_city_label || "").trim();
    const destinationLabel = (order?.delivery_destination_label || "").trim();
    const fallbackAddress = (order?.delivery_address || "").trim();
    const parsed = splitDeliveryAddress(fallbackAddress);
    const resolvedCity = formatCityWithRegion(cityLabel || parsed.city, parsed.region);
    const rawDestination = destinationLabel || parsed.destination || fallbackAddress;
    const normalizedDestination = normalizeDeliveryDestination(rawDestination, resolvedCity);

    const resolvedDestination = deliveryMethod === "nova_poshta"
      ? formatNovaPoshtaDestination(rawDestination, resolvedCity, t) || normalizedDestination
      : normalizedDestination;

    return {
      city: resolvedCity || "-",
      destination: resolvedDestination || "-",
    };
  }, [order?.delivery_address, order?.delivery_city_label, order?.delivery_destination_label, order?.delivery_method, t]);

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
                      {isMonobankPayment && order.payment?.page_url ? (
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
                          <RefreshCw className={`h-4 w-4 ${paymentRefreshing ? "animate-spin" : ""}`} />
                        </button>
                      ) : null}
                    </div>
                  </div>

                  <div className="mt-3 grid gap-2">
                    <ValueField
                      label={t("orders.payment.method")}
                      value={resolvePaymentMethodLabel(order.payment?.method || "", t)}
                    />
                    <ValueField
                      label={t("orders.payment.status")}
                      value={resolvePaymentStatusLabel(order.payment?.status || "", t)}
                    />
                    <ValueField
                      label={t("orders.payment.amount")}
                      value={order.payment ? `${order.payment.amount} ${order.payment.currency}` : "-"}
                      bold
                    />
                    <ValueField label={t("orders.payment.lastSyncAt")} value={formatBackofficeDate(order.payment?.last_sync_at)} />
                    {isMonobankPayment ? (
                      <>
                        <ValueField label={t("orders.payment.invoiceId")} value={order.payment?.invoice_id || "-"} mono />
                        <ValueField label={t("orders.payment.reference")} value={order.payment?.reference || "-"} />
                        <ValueField label={t("orders.payment.failureReason")} value={order.payment?.failure_reason || "-"} />
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
                    <ValueField label={t("orders.modals.view.summary.fullName")} value={order.contact_full_name || "-"} bold />
                    <ValueField label="Email" value={order.contact_email || order.user_email || "-"} />
                    <ValueField label={t("orders.modals.view.summary.phone")} value={order.contact_phone || "-"} />
                    <ValueField label={t("orders.modals.view.summary.deliveryCity")} value={deliveryAddressParts.city} />
                    <ValueField label={t("orders.modals.view.summary.deliveryDestination")} value={deliveryAddressParts.destination} />
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
                          disabled={Boolean(actionLoading)}
                          aria-label={activeActionLabel}
                        >
                          <RefreshCw className={`h-4 w-4 ${actionLoading ? "animate-spin" : ""}`} />
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
                    <ValueField label={deliveryMethodLabel} value={resolveDeliveryMethodLabel(order.delivery_method, t)} />
                    <ValueField label={paymentMethodLabel} value={resolveOrderPaymentMethodLabel(order.payment_method, t)} />
                    <ValueField label={t("orders.table.columns.created")} value={formatOrderDate(order.placed_at)} />
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
