"use client";

import { useTranslations } from "next-intl";

export function GarageEmptyState() {
  const t = useTranslations("garage.empty");

  return (
    <div className="rounded-xl border p-5" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <h2 className="text-lg font-semibold">{t("title")}</h2>
      <p className="mt-2 text-sm" style={{ color: "var(--muted)" }}>
        {t("description")}
      </p>
    </div>
  );
}
