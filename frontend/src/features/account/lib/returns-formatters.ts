export function formatReturnDate(value: string, locale: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

export function formatReturnMoney(value: string, locale: string, currency = "UAH"): string {
  const amount = Number(value);
  if (!Number.isFinite(amount)) {
    return `${value} ${currency}`;
  }
  return `${new Intl.NumberFormat(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(amount)} ${currency}`;
}

export function normalizeTrackingDigits(value: string): string {
  const digits = String(value || "").replace(/\D+/g, "");
  return digits.slice(0, 14);
}

export function formatTrackingNumber(value: string): string {
  const digits = normalizeTrackingDigits(value);
  const parts = [
    digits.slice(0, 2),
    digits.slice(2, 6),
    digits.slice(6, 10),
    digits.slice(10, 14),
  ].filter(Boolean);
  return parts.join(" ");
}
