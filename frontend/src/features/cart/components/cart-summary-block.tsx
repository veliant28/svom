"use client";

import { useTranslations } from "next-intl";

export function CartSummaryBlock({
  itemsCount,
  subtotal,
  currency,
}: {
  itemsCount: number;
  subtotal: string;
  currency: string;
}) {
  const t = useTranslations("commerce.cart");

  return (
    <aside className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <h2 className="text-lg font-semibold">{t("summary.title")}</h2>
      <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
        {t("summary.items", { count: itemsCount })}
      </p>
      <p className="mt-2 text-xl font-semibold">
        {subtotal} {currency}
      </p>
    </aside>
  );
}
