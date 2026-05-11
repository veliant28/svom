"use client";

import { Clock3, X } from "lucide-react";
import { createPortal } from "react-dom";

import type { SecurityActor, SecurityEvent } from "@/features/backoffice/security/types/security.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

function formatDateTime(value: string, locale: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function SecurityHistoryModal({
  actor,
  events,
  isLoading,
  locale,
  t,
  onClose,
}: {
  actor: SecurityActor | null;
  events: SecurityEvent[];
  isLoading: boolean;
  locale: string;
  t: Translator;
  onClose: () => void;
}) {
  if (!actor || typeof document === "undefined") {
    return null;
  }
  return createPortal(
    <div className="fixed inset-0 z-[1450] flex items-center justify-center bg-black/45 px-3 py-4" onClick={onClose}>
      <div className="w-full max-w-3xl overflow-hidden rounded-xl border shadow-2xl" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }} onClick={(event) => event.stopPropagation()}>
        <header className="flex items-center justify-between border-b px-4 py-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
          <div className="min-w-0">
            <p className="text-sm font-semibold">{t("modals.history.title")}</p>
            <p className="truncate text-xs" style={{ color: "var(--muted)" }}>{actor.source_identifier}</p>
          </div>
          <button type="button" className="rounded-md border p-2" style={{ borderColor: "var(--border)" }} aria-label={t("actions.close")} onClick={onClose}>
            <X className="size-4" />
          </button>
        </header>
        <div className="max-h-[70vh] overflow-y-auto px-4 py-4">
          {isLoading ? (
            <div className="flex items-center gap-2 text-sm" style={{ color: "var(--muted)" }}><Clock3 className="size-4 animate-spin" />{t("loading")}</div>
          ) : !events.length ? (
            <p className="text-sm" style={{ color: "var(--muted)" }}>{t("empty.history")}</p>
          ) : (
            <ol>
              {events.map((event, index) => (
                <li key={event.id} className="relative pb-5 pl-10 last:pb-0">
                  {index > 0 ? (
                    <span className="absolute left-4 top-0 h-3 w-px -translate-x-1/2" style={{ backgroundColor: "var(--border)" }} />
                  ) : null}
                  {index < events.length - 1 ? (
                    <span className="absolute bottom-0 left-4 top-3 w-px -translate-x-1/2" style={{ backgroundColor: "var(--border)" }} />
                  ) : null}
                  <span
                    className="absolute left-4 top-1 inline-flex h-4 w-4 -translate-x-1/2 items-center justify-center rounded-full border-2 border-blue-600 bg-blue-600"
                    style={index === 0 ? { boxShadow: "0 0 0 4px rgba(37,99,235,.2)" } : undefined}
                  />
                  <div className="rounded-lg border p-3" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
                    <div className="flex flex-wrap justify-between gap-2">
                      <p className="font-semibold">{t(`eventTypes.${event.event_type}`)}</p>
                      <p className="text-xs" style={{ color: "var(--muted)" }}>{formatDateTime(event.created_at, locale)}</p>
                    </div>
                    <p className="mt-1 truncate text-xs" style={{ color: "var(--muted)" }}>
                      {[event.method, event.endpoint, event.status_code ? String(event.status_code) : ""].filter(Boolean).join(t("punctuation.separator"))}
                    </p>
                    {event.user_agent ? <p className="mt-1 truncate text-xs" style={{ color: "var(--muted)" }}>{event.user_agent}</p> : null}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
