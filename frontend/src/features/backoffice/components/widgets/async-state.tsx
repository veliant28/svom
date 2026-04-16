"use client";

import { CircleAlert } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslations } from "next-intl";

export function AsyncState({
  isLoading,
  error,
  empty,
  emptyLabel,
  children,
}: {
  isLoading: boolean;
  error: string | null;
  empty: boolean;
  emptyLabel: string;
  children: ReactNode;
}) {
  const t = useTranslations("backoffice.common");

  if (isLoading) {
    return (
      <div className="rounded-xl border p-6 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        {t("loading")}
      </div>
    );
  }

  if (error) {
    return (
      <div
        role="alert"
        className="rounded-xl border p-4 text-sm"
        style={{
          borderColor: "#fda4af",
          background: "linear-gradient(135deg, #fff4f6 0%, #fff0f1 100%)",
          color: "#881337",
        }}
      >
        <div className="flex items-center gap-2.5">
          <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-rose-100 text-rose-700">
            <CircleAlert size={18} />
          </span>
          <p className="flex-1 leading-snug">{error}</p>
        </div>
      </div>
    );
  }

  if (empty) {
    return (
      <div className="rounded-xl border p-6 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        {emptyLabel}
      </div>
    );
  }

  return <>{children}</>;
}
