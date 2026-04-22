"use client";

import { CheckCircle2, MinusCircle } from "lucide-react";
import { useTranslations } from "next-intl";

import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { SupportStatusChip } from "@/features/support/components/support-status-chip";
import type { SupportThread, SupportUser } from "@/features/support/types";

function formatDateTime(value: string | null): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function SupportUserBlock({ label, user }: { label: string; user: SupportUser | null }) {
  const t = useTranslations("backoffice.common.support.shared");
  return (
    <div>
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>{label}</p>
        {user ? (
          <BackofficeStatusChip
            tone={user.is_online ? "success" : "gray"}
            icon={user.is_online ? CheckCircle2 : MinusCircle}
          >
            {user.is_online ? t("online") : t("offline")}
          </BackofficeStatusChip>
        ) : null}
      </div>
      <p className="mt-1 text-sm font-semibold">{user?.full_name || "-"}</p>
      {user?.email ? <p className="text-xs" style={{ color: "var(--muted)" }}>{user.email}</p> : null}
    </div>
  );
}

export function SupportThreadDetails({ thread }: { thread: SupportThread | null }) {
  const t = useTranslations("backoffice.common.support.shared");

  if (!thread) {
    return (
      <div className="rounded-xl border p-4 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        {t("selectThread")}
      </div>
    );
  }

  return (
    <div className="min-w-0 rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="break-words text-sm font-semibold">{thread.subject}</p>
          <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>#{thread.id.slice(0, 8)}</p>
        </div>
        <SupportStatusChip status={thread.status} />
      </div>

      <div className="mt-4 grid gap-4">
        <SupportUserBlock label={t("customer")} user={thread.customer} />
        <SupportUserBlock label={t("assigned")} user={thread.assigned_staff} />
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>{t("lastActivity")}</p>
          <p className="mt-1 text-sm">{formatDateTime(thread.last_message_at)}</p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--muted)" }}>{t("firstResponse")}</p>
          <p className="mt-1 text-sm">{formatDateTime(thread.first_response_at)}</p>
        </div>
      </div>
    </div>
  );
}
