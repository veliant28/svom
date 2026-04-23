export function formatMoney(value: string, currency: string, locale: string): string {
  const amount = Number(value);
  if (Number.isNaN(amount)) {
    return `${value} ${currency}`;
  }

  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount) + ` ${currency}`;
}

export function formatDateTime(value: string, locale: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function resolveOrderStatusTone(status: string): "success" | "warning" | "danger" | "neutral" {
  if (status === "completed" || status === "shipped" || status === "ready_for_shipment") {
    return "success";
  }
  if (status === "cancelled") {
    return "danger";
  }
  if (status === "processing") {
    return "warning";
  }
  return "neutral";
}

export function resolveOrderStatusChipTone(status: string): "success" | "warning" | "error" | "info" {
  const tone = resolveOrderStatusTone(status);
  if (tone === "success") {
    return "success";
  }
  if (tone === "warning") {
    return "warning";
  }
  if (tone === "danger") {
    return "error";
  }
  return "info";
}
