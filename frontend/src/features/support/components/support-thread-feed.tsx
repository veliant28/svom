"use client";

import { useEffect, useRef } from "react";
import { useTranslations } from "next-intl";

import type { SupportMessage, SupportTypingPayload } from "@/features/support/types";

function formatSystemEvent(message: SupportMessage, t: ReturnType<typeof useTranslations>): string {
  const rawStatus = String(message.event_payload?.status || "-");
  const normalizedStatus = rawStatus === "waiting_for_support" || rawStatus === "waiting_for_client" ? "open" : rawStatus;
  let statusLabel = rawStatus;
  if (normalizedStatus && normalizedStatus !== "-") {
    try {
      statusLabel = t(`statusValues.${normalizedStatus}`);
    } catch {
      statusLabel = normalizedStatus;
    }
  }
  if (message.event_code === "thread.assigned.manual") {
    return t("systemEvents.assignedManual");
  }
  if (message.event_code === "thread.assigned.auto_reply") {
    return t("systemEvents.assignedAutoReply");
  }
  if (message.event_code === "thread.reassigned.manual") {
    return t("systemEvents.reassignedManual");
  }
  if (message.event_code === "thread.reassigned.auto_reply") {
    return t("systemEvents.reassignedAutoReply");
  }
  if (message.event_code === "thread.status_changed") {
    return t("systemEvents.statusChanged", { status: statusLabel });
  }
  return message.event_code || t("systemEvents.generic");
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function SupportThreadFeed({
  currentSide,
  messages,
  typing,
  emptyLabel,
}: {
  currentSide: "customer" | "staff";
  messages: SupportMessage[];
  typing: SupportTypingPayload | null;
  emptyLabel: string;
}) {
  const t = useTranslations("backoffice.common.support.shared");
  const containerRef = useRef<HTMLDivElement | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }
    const nearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 96;
    if (nearBottom) {
      bottomRef.current?.scrollIntoView({ block: "end" });
    }
  }, [messages, typing]);

  if (!messages.length) {
    return (
      <div className="rounded-xl border p-4 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        {emptyLabel}
      </div>
    );
  }

  const oppositeTyping = currentSide === "customer" ? typing?.staff_users ?? [] : typing?.customer_users ?? [];

  return (
    <div ref={containerRef} className="flex min-h-0 min-w-0 flex-1 flex-col gap-3 overflow-x-hidden overflow-y-auto rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      {messages.map((message) => {
        if (message.kind === "system_event") {
          return (
            <div key={message.id} className="mx-auto max-w-[80%] rounded-md border px-3 py-1 text-center text-xs" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)", color: "var(--muted)" }}>
              {formatSystemEvent(message, t)}
            </div>
          );
        }

        const isOwn = message.author_side === currentSide;
        return (
          <div key={message.id} className={`flex ${isOwn ? "justify-end" : "justify-start"}`}>
            <div
              className="max-w-[82%] min-w-0 rounded-md px-3 py-2"
              style={{
                backgroundColor: isOwn ? "rgba(37,99,235,0.12)" : "var(--surface-2)",
                border: `1px solid ${isOwn ? "rgba(37,99,235,0.2)" : "var(--border)"}`,
              }}
            >
              <p className="text-xs font-semibold" style={{ color: "var(--muted)" }}>
                {message.author?.full_name || message.author?.email || message.author_side}
              </p>
              <p className="mt-1 whitespace-pre-wrap break-words text-sm">{message.body}</p>
              <p className="mt-2 text-[11px]" style={{ color: "var(--muted)" }}>
                {formatTimestamp(message.created_at)}
              </p>
            </div>
          </div>
        );
      })}
      {oppositeTyping.length ? (
        <div className="text-xs" style={{ color: "var(--muted)" }}>
          {t("typing", { users: oppositeTyping.map((user) => user.full_name).join(", ") })}
        </div>
      ) : null}
      <div ref={bottomRef} />
    </div>
  );
}
