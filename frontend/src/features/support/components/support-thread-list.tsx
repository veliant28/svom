"use client";

import { MessageSquareText } from "lucide-react";
import { useTranslations } from "next-intl";

import { SupportStatusChip } from "@/features/support/components/support-status-chip";
import type { SupportThread } from "@/features/support/types";

export function SupportThreadList({
  mode,
  items,
  selectedThreadId,
  onSelect,
  emptyLabel,
  heightClassName = "h-[680px]",
}: {
  mode: "customer" | "staff";
  items: SupportThread[];
  selectedThreadId: string | null;
  onSelect: (threadId: string) => void;
  emptyLabel: string;
  heightClassName?: string;
}) {
  const t = useTranslations("backoffice.common.support.shared");

  if (!items.length) {
    return (
      <div className={`${heightClassName} min-w-0 overflow-y-auto text-sm`} style={{ color: "var(--muted)" }}>
        <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
          {emptyLabel}
        </div>
      </div>
    );
  }

  return (
    <div className={`${heightClassName} min-w-0 overflow-y-auto`}>
      <div className="grid min-w-0 gap-2">
        {items.map((thread) => {
          const isSelected = thread.id === selectedThreadId;
          const counterpart = mode === "staff" ? thread.customer : thread.assigned_staff;
          return (
            <button
              key={thread.id}
              type="button"
              onClick={() => onSelect(thread.id)}
              className="w-full min-w-0 min-h-[132px] rounded-xl border p-3 text-left transition-colors"
              style={{
                borderColor: isSelected ? "#2563eb" : "var(--border)",
                backgroundColor: isSelected ? "rgba(37,99,235,0.08)" : "var(--surface)",
              }}
            >
              <div className="flex items-start gap-2">
                <p className="min-w-0 flex-1 truncate text-sm font-semibold">{thread.subject}</p>
                <div className="shrink-0">
                  <SupportStatusChip status={thread.status} />
                </div>
              </div>
              <p className="mt-1 truncate text-xs" style={{ color: "var(--muted)" }}>
                {counterpart?.full_name || counterpart?.email || thread.customer.full_name}
              </p>
              <div className="mt-2 flex items-start gap-2 text-xs" style={{ color: "var(--muted)" }}>
                <MessageSquareText size={13} className="mt-0.5 shrink-0" />
                <span className="line-clamp-2">{thread.latest_message_preview || "-"}</span>
              </div>
              <div className="mt-2 flex min-h-5 justify-end gap-1.5">
                {thread.is_mine ? (
                  <span
                    className="inline-flex h-5 items-center rounded-md border px-1.5 text-[10px] font-semibold"
                    style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--text)" }}
                  >
                    {t("mine")}
                  </span>
                ) : null}
                {thread.unread_count ? (
                  <span className="inline-flex min-w-6 items-center justify-center rounded-full bg-blue-600 px-1.5 py-0.5 text-[11px] font-semibold text-white">
                    {thread.unread_count}
                  </span>
                ) : null}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
