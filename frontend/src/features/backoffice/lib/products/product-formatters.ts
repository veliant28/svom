export function formatProductPrice(value: string | null, currency: string | null, locale: string): string {
  const normalized = String(value ?? "").trim();
  if (!normalized) {
    return "-";
  }

  const parsed = Number(normalized);
  const amount = Number.isFinite(parsed)
    ? new Intl.NumberFormat(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(parsed)
    : normalized;
  return `${amount} ${currency || "UAH"}`.trim();
}
