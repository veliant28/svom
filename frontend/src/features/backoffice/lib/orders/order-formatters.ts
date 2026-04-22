import { formatBackofficeDate } from "@/features/backoffice/lib/supplier-workspace";

export function formatOrderDate(value: string | null | undefined): string {
  const formatted = formatBackofficeDate(value);
  return formatted.replace(/,\s+/g, " ");
}

export function formatOrderTotal(value: string | number | null | undefined, currency: string, locale: string): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  const numeric = typeof value === "number" ? value : Number(String(value));
  if (Number.isFinite(numeric)) {
    try {
      return new Intl.NumberFormat(locale, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(numeric);
    } catch {
      return `${numeric.toFixed(2)} ${currency}`;
    }
  }

  return `${String(value)} ${currency}`;
}

export function formatOrderTotalWithCurrency(
  value: string | number | null | undefined,
  currency: string,
  locale: string,
): string {
  const amount = formatOrderTotal(value, currency, locale);
  return amount === "-" ? amount : `${amount} ${currency}`;
}

export function resolveOrderStatusDescription(
  status: string,
  t: (key: string, values?: Record<string, string | number>) => string,
): string {
  const normalized = status.trim().toLowerCase();
  const byStatus: Record<string, string> = {
    new: "orders.statusDescriptions.new",
    confirmed: "orders.statusDescriptions.confirmed",
    awaiting_procurement: "orders.statusDescriptions.awaiting_procurement",
    reserved: "orders.statusDescriptions.reserved",
    partially_reserved: "orders.statusDescriptions.partially_reserved",
    ready_to_ship: "orders.statusDescriptions.ready_to_ship",
    shipped: "orders.statusDescriptions.shipped",
    completed: "orders.statusDescriptions.completed",
    cancelled: "orders.statusDescriptions.cancelled",
  };

  const key = byStatus[normalized] ?? "orders.statusDescriptions.default";
  return t(key);
}
