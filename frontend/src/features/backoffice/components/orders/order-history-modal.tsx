import { ArrowRight, Clock3, X } from "lucide-react";
import { createPortal } from "react-dom";
import type { CSSProperties } from "react";

import { RoleGroupBadge } from "@/features/backoffice/components/rbac/role-group-badge";
import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import { StatusChip } from "@/features/backoffice/components/widgets/status-chip";
import type { BackofficeOrderHistoryEvent } from "@/features/backoffice/types/orders.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

function formatDateTime(value: string, locale: string): string {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return "—";
  }
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) {
    return normalized;
  }
  return new Intl.DateTimeFormat(locale || "uk", { dateStyle: "medium", timeStyle: "short" }).format(parsed);
}

function resolveStepMarkerStyle(index: number): CSSProperties {
  if (index === 0) {
    return {
      width: "0.875rem",
      height: "0.875rem",
      borderRadius: "9999px",
      border: "2px solid #2563eb",
      backgroundColor: "#2563eb",
      boxShadow: "0 0 0 4px rgba(37,99,235,.2)",
    };
  }
  return {
    width: "0.875rem",
    height: "0.875rem",
    borderRadius: "9999px",
    border: "2px solid #94a3b8",
    backgroundColor: "#e2e8f0",
  };
}

export function OrderHistoryModal({
  isOpen,
  title,
  subtitle,
  locale,
  events,
  isLoading,
  emptyLabel,
  t,
  onClose,
}: {
  isOpen: boolean;
  title: string;
  subtitle: string;
  locale: string;
  events: BackofficeOrderHistoryEvent[];
  isLoading: boolean;
  emptyLabel: string;
  t: Translator;
  onClose: () => void;
}) {
  if (!isOpen || typeof document === "undefined") {
    return null;
  }

  return createPortal(
    <div
      className="fixed inset-0 z-[1400] flex items-center justify-center bg-black/45 px-3 py-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl overflow-hidden rounded-xl border shadow-2xl"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--text)" }}
        onClick={(event) => event.stopPropagation()}
      >
        <header
          className="flex items-center justify-between border-b px-4 py-3"
          style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
        >
          <div className="min-w-0">
            <p className="text-sm font-semibold">{title}</p>
            <p className="mt-0.5 truncate text-xs" style={{ color: "var(--muted)" }}>
              {subtitle}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
            aria-label={t("orders.actions.closeModal")}
          >
            <X className="size-4" />
          </button>
        </header>

        <div className="max-h-[70vh] overflow-y-auto px-4 py-4">
          {isLoading ? (
            <div className="flex items-center gap-2 text-sm" style={{ color: "var(--muted)" }}>
              <Clock3 className="size-4 animate-spin" />
              <span>{t("loading")}</span>
            </div>
          ) : !events.length ? (
            <p className="text-sm" style={{ color: "var(--muted)" }}>
              {emptyLabel}
            </p>
          ) : (
            <ol className="grid gap-0">
              {events.map((event, index) => {
                const isFirst = index === 0;
                const isLast = index === events.length - 1;
                const payload = event.payload ?? {};
                const fromStatus = typeof payload.from_status === "string" ? payload.from_status : "";
                const toStatus = typeof payload.to_status === "string" ? payload.to_status : "";
                const hasStatusTransition = event.event_type === "status_change" && Boolean(fromStatus || toStatus);
                const eventTitle = hasStatusTransition ? t("orders.history.statusChanged") : (event.action || event.event_label || "—");

                return (
                  <li key={event.id} className="relative pb-5 pl-11 last:pb-0">
                    {!isFirst ? (
                      <span
                        aria-hidden="true"
                        className="absolute left-4 top-0 h-[1.125rem] w-px -translate-x-1/2"
                        style={{ backgroundColor: "#cbd5e1" }}
                      />
                    ) : null}
                    {!isLast ? (
                      <span
                        aria-hidden="true"
                        className="absolute bottom-0 left-4 top-[1.125rem] w-px -translate-x-1/2"
                        style={{ backgroundColor: "#cbd5e1" }}
                      />
                    ) : null}
                    <span
                      aria-hidden="true"
                      className="absolute left-4 top-1.5 inline-flex h-6 w-6 -translate-x-1/2 items-center justify-center bg-transparent"
                    >
                      <span style={resolveStepMarkerStyle(index)} />
                    </span>
                    <div
                      className="grid gap-2 rounded-lg border px-3 py-3"
                      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
                    >
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-sm font-semibold">{eventTitle}</p>
                          <div className="mt-0.5 text-xs" style={{ color: "var(--muted)" }}>
                            {formatDateTime(event.occurred_at, locale)}
                          </div>
                        </div>
                        {event.actor ? (
                          <div className="min-w-0 text-right">
                            {event.actor.role_group_name ? (
                              <RoleGroupBadge groupName={event.actor.role_group_name} />
                            ) : null}
                            {event.actor.full_name ? (
                              <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>
                                {event.actor.full_name}
                              </p>
                            ) : null}
                          </div>
                        ) : null}
                      </div>

                      {hasStatusTransition ? (
                        <div className="grid gap-1 text-xs">
                          <div className="flex flex-wrap items-center gap-2">
                            <StatusChip status={fromStatus || "unknown"} />
                            <BackofficeStatusChip
                              tone="warning"
                              icon={ArrowRight}
                              className="justify-center gap-0 px-1.5 border-amber-500/70 bg-amber-400/35 text-amber-900 dark:border-amber-300/75 dark:bg-amber-300/30 dark:text-amber-50 [&>span:last-child]:hidden"
                            >
                              <span className="sr-only">{t("orders.history.statusChanged")}</span>
                            </BackofficeStatusChip>
                            <StatusChip status={toStatus || "unknown"} />
                          </div>
                        </div>
                      ) : null}

                      {event.message ? (
                        <p className="text-xs" style={{ color: "var(--muted)" }}>
                          {event.message}
                        </p>
                      ) : null}
                    </div>
                  </li>
                );
              })}
            </ol>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
