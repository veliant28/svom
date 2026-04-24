import { CheckCircle2, Clock3, Info, ScanBarcode, ScanLine, Truck, TriangleAlert, X } from "lucide-react";
import { createPortal } from "react-dom";
import type { CSSProperties } from "react";

import { BackofficeStatusChip } from "@/features/backoffice/components/widgets/backoffice-status-chip";
import type { BackofficeOrderNovaPoshtaWaybill } from "@/features/backoffice/types/nova-poshta.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

type TrackingProgressState = "completed" | "current" | "upcoming";

type TrackingTimelineStep = {
  id: string;
  statusCode: string;
  statusLabel: string;
  location: string;
  warehouse: string;
  note: string;
  comment: string;
  eventAt: string;
  syncedAt: string;
  progressState: TrackingProgressState;
  isSynthetic: boolean;
};

const WAYBILL_STATUS_CATALOG_CODES = new Set([
  "1", "2", "3", "4", "41", "5", "6", "7", "8", "9", "10", "11", "12", "101", "102", "103", "104", "105", "106", "111", "112",
]);

const TRACKING_STATUS_PROGRESS_FLOW = [
  "1", "4", "41", "5", "101", "6", "7", "8", "9", "10", "11", "106",
];

const DANGER_STATUS_CODES = new Set(["2", "3", "102", "103", "105", "111"]);
const SUCCESS_STATUS_CODES = new Set(["9", "10", "11", "106"]);
const WARNING_STATUS_CODES = new Set(["1", "12"]);

function parseDateMs(value: string): number | null {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return null;
  }
  const parsed = Date.parse(normalized);
  return Number.isNaN(parsed) ? null : parsed;
}

function formatDateTime(value: string, locale: string): string {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return "—";
  }
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) {
    return normalized;
  }
  return new Intl.DateTimeFormat(locale || "uk", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function resolveTrackingStatusLabel(t: Translator, statusCode: string, statusText: string): string {
  const code = String(statusCode || "").trim();
  const text = String(statusText || "").trim();
  if (code && WAYBILL_STATUS_CATALOG_CODES.has(code)) {
    return t(`orders.table.waybillStatusCatalog.${code}.full`);
  }
  return text || code || t("orders.table.waybillStatusUnknown");
}

function resolveStatusTone(code: string): "success" | "danger" | "warning" | "info" {
  const normalized = String(code || "").trim();
  if (DANGER_STATUS_CODES.has(normalized)) {
    return "danger";
  }
  if (SUCCESS_STATUS_CODES.has(normalized)) {
    return "success";
  }
  if (WARNING_STATUS_CODES.has(normalized)) {
    return "warning";
  }
  return "info";
}

function resolveStatusIcon(tone: "success" | "danger" | "warning" | "info") {
  if (tone === "success") {
    return <CheckCircle2 className="size-4" />;
  }
  if (tone === "danger") {
    return <TriangleAlert className="size-4" />;
  }
  if (tone === "warning") {
    return <Clock3 className="size-4" />;
  }
  if (tone === "info") {
    return <Truck className="size-4" />;
  }
  return <Info className="size-4" />;
}

function resolveStatusIconStyle(tone: "success" | "danger" | "warning" | "info"): CSSProperties {
  if (tone === "success") {
    return { borderColor: "#10b981", backgroundColor: "rgba(16,185,129,.12)", color: "#047857" };
  }
  if (tone === "danger") {
    return { borderColor: "#ef4444", backgroundColor: "rgba(239,68,68,.12)", color: "#b91c1c" };
  }
  if (tone === "warning") {
    return { borderColor: "#f59e0b", backgroundColor: "rgba(245,158,11,.12)", color: "#b45309" };
  }
  return { borderColor: "#3b82f6", backgroundColor: "rgba(59,130,246,.12)", color: "#1d4ed8" };
}

function buildTrackingTimeline(waybill: BackofficeOrderNovaPoshtaWaybill, t: Translator): TrackingTimelineStep[] {
  const rows = Array.isArray(waybill.tracking_events) ? waybill.tracking_events : [];
  const mappedEvents = rows
    .map((item) => {
      const code = String(item.status_code || "").trim();
      const text = String(item.status_text || "").trim();
      return {
        id: String(item.id || ""),
        statusCode: code,
        statusLabel: resolveTrackingStatusLabel(t, code, text),
        location: String(item.location || "").trim(),
        warehouse: String(item.warehouse || "").trim(),
        note: String(item.note || "").trim(),
        comment: String(item.comment || "").trim(),
        eventAt: String(item.event_at || "").trim(),
        syncedAt: String(item.synced_at || "").trim(),
      };
    })
    .filter((item) => item.statusCode || item.statusLabel)
    .sort((left, right) => {
      const leftMs = parseDateMs(left.eventAt || left.syncedAt);
      const rightMs = parseDateMs(right.eventAt || right.syncedAt);
      if (leftMs === null && rightMs === null) {
        return 0;
      }
      if (leftMs === null) {
        return 1;
      }
      if (rightMs === null) {
        return -1;
      }
      return rightMs - leftMs;
    });

  const dedupedEvents: typeof mappedEvents = [];
  const seenSnapshots = new Set<string>();
  for (const event of mappedEvents) {
    const snapshotKey = [
      event.statusCode,
      event.statusLabel,
      event.location,
      event.warehouse,
      event.note,
      event.comment,
    ].join("|").toLowerCase();
    if (seenSnapshots.has(snapshotKey)) {
      continue;
    }
    seenSnapshots.add(snapshotKey);
    dedupedEvents.push(event);
  }

  const events = dedupedEvents
    .sort((left, right) => {
      const leftMs = parseDateMs(left.eventAt || left.syncedAt);
      const rightMs = parseDateMs(right.eventAt || right.syncedAt);
      if (leftMs === null && rightMs === null) {
        return 0;
      }
      if (leftMs === null) {
        return 1;
      }
      if (rightMs === null) {
        return -1;
      }
      return leftMs - rightMs;
    });

  if (!events.length && (waybill.status_code || waybill.status_text)) {
    events.push({
      id: `fallback-${waybill.id}`,
      statusCode: String(waybill.status_code || "").trim(),
      statusLabel: resolveTrackingStatusLabel(t, String(waybill.status_code || ""), String(waybill.status_text || "")),
      location: "",
      warehouse: "",
      note: "",
      comment: "",
      eventAt: String(waybill.status_synced_at || "").trim(),
      syncedAt: String(waybill.status_synced_at || "").trim(),
    });
  }

  if (!events.length) {
    return [];
  }

  const currentCode = String(waybill.status_code || "").trim();
  const currentIndex = currentCode
    ? Math.max(...events.map((row, index) => (row.statusCode === currentCode ? index : -1)))
    : events.length - 1;
  const normalizedCurrentIndex = currentIndex >= 0 ? currentIndex : events.length - 1;

  const steps: TrackingTimelineStep[] = events.map((entry, index) => ({
    ...entry,
    progressState: index < normalizedCurrentIndex ? "completed" : index === normalizedCurrentIndex ? "current" : "upcoming",
    isSynthetic: false,
  }));

  const flowIndex = TRACKING_STATUS_PROGRESS_FLOW.indexOf(currentCode);
  if (flowIndex < 0) {
    return steps;
  }
  const existingCodes = new Set(events.map((row) => row.statusCode).filter(Boolean));
  const futureCodes = TRACKING_STATUS_PROGRESS_FLOW.slice(flowIndex + 1).filter((code) => !existingCodes.has(code)).slice(0, 4);
  for (const code of futureCodes) {
    steps.push({
      id: `future-${code}`,
      statusCode: code,
      statusLabel: resolveTrackingStatusLabel(t, code, ""),
      location: "",
      warehouse: "",
      note: "",
      comment: "",
      eventAt: "",
      syncedAt: "",
      progressState: "upcoming",
      isSynthetic: true,
    });
  }
  return steps;
}

function resolveConnectorStyle(current: TrackingProgressState, next: TrackingProgressState | null): CSSProperties {
  if (current === "completed" && next && next !== "upcoming") {
    return { backgroundColor: "#10b981" };
  }
  return { backgroundColor: "#cbd5e1" };
}

function resolveMarkerStyle(state: TrackingProgressState): CSSProperties {
  if (state === "completed") {
    return {
      width: "0.875rem",
      height: "0.875rem",
      borderRadius: "9999px",
      border: "2px solid #10b981",
      backgroundColor: "#10b981",
    };
  }
  if (state === "current") {
    return {
      width: "0.875rem",
      height: "0.875rem",
      borderRadius: "9999px",
      border: "2px solid #10b981",
      backgroundColor: "#10b981",
      boxShadow: "0 0 0 4px rgba(16,185,129,.2)",
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

function resolveStepLabelStyle(state: TrackingProgressState): CSSProperties {
  if (state === "current") {
    return { color: "var(--text)", fontWeight: 600 };
  }
  if (state === "completed") {
    return { color: "var(--text)", fontWeight: 500 };
  }
  return { color: "var(--muted)" };
}

export function OrderWaybillTrackingModal({
  isOpen,
  waybill,
  locale,
  t,
  onClose,
}: {
  isOpen: boolean;
  waybill: BackofficeOrderNovaPoshtaWaybill | null;
  locale: string;
  t: Translator;
  onClose: () => void;
}) {
  if (!isOpen || !waybill || typeof document === "undefined") {
    return null;
  }

  const currentCode = String(waybill.status_code || "").trim();
  const currentText = String(waybill.status_text || "").trim();
  const currentStatusLabel = resolveTrackingStatusLabel(t, currentCode, currentText);
  const currentTone = resolveStatusTone(currentCode);
  const timeline = buildTrackingTimeline(waybill, t);
  const syncedAt = String(waybill.status_synced_at || "").trim() || (timeline[timeline.length - 1]?.syncedAt || "");

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
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <p className="text-sm font-semibold">{t("orders.modals.waybill.tracking.title")}</p>
            <BackofficeStatusChip
              tone={waybill.np_number ? "success" : "orange"}
              icon={waybill.np_number ? ScanBarcode : ScanLine}
              className="h-7 px-2 py-0 tracking-wide"
            >
              {waybill.np_number || t("orders.table.waybillEmpty")}
            </BackofficeStatusChip>
          </div>
          <button
            type="button"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)", color: "var(--muted)" }}
            onClick={onClose}
            aria-label={t("orders.modals.waybill.tracking.close")}
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="grid max-h-[78vh] gap-4 overflow-y-auto p-4">
          <div
            className="rounded-lg border p-3"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          >
            <div className="mb-2 flex items-center gap-3">
              <span
                className="inline-flex h-8 w-8 items-center justify-center rounded-md border"
                style={resolveStatusIconStyle(currentTone)}
              >
                {resolveStatusIcon(currentTone)}
              </span>
              <div className="min-w-0">
                <p className="text-xs" style={{ color: "var(--muted)" }}>
                  {t("orders.modals.waybill.tracking.currentStatus")}
                </p>
                <p className="text-sm font-semibold">{currentStatusLabel}</p>
              </div>
            </div>
            <p className="text-xs" style={{ color: "var(--muted)" }}>
              {t("orders.modals.waybill.tracking.syncedAt")}: {formatDateTime(syncedAt, locale)}
            </p>
          </div>

          {!timeline.length ? (
            <p className="text-sm" style={{ color: "var(--muted)" }}>
              {t("orders.modals.waybill.tracking.empty")}
            </p>
          ) : (
            <ol className="grid gap-0">
              {timeline.map((step, index) => {
                const isLast = index === timeline.length - 1;
                const nextStep = isLast ? null : timeline[index + 1];
                const locationLine = [step.location, step.warehouse].filter(Boolean).join(" · ");
                return (
                  <li key={step.id} className="relative pb-5 pl-11 last:pb-0">
                    {!isLast ? (
                      <span
                        aria-hidden="true"
                        className="absolute bottom-0 left-4 top-6 w-px -translate-x-1/2"
                        style={resolveConnectorStyle(step.progressState, nextStep?.progressState ?? null)}
                      />
                    ) : null}
                    <span
                      aria-hidden="true"
                      className="absolute left-4 top-1.5 inline-flex h-6 w-6 -translate-x-1/2 items-center justify-center"
                    >
                      <span style={resolveMarkerStyle(step.progressState)} />
                    </span>
                    <div className="grid gap-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm" style={resolveStepLabelStyle(step.progressState)}>
                          {step.statusLabel}
                        </span>
                        <span className="text-xs" style={{ color: "var(--muted)" }}>
                          {step.isSynthetic ? t("orders.modals.waybill.tracking.planned") : formatDateTime(step.eventAt || step.syncedAt, locale)}
                        </span>
                      </div>
                      {locationLine ? (
                        <p className="text-xs" style={{ color: "var(--muted)" }}>
                          {locationLine}
                        </p>
                      ) : null}
                      {step.note ? (
                        <p className="text-xs" style={{ color: "var(--muted)" }}>
                          {step.note}
                        </p>
                      ) : null}
                      {step.comment ? (
                        <p className="text-xs" style={{ color: "var(--muted)" }}>
                          {step.comment}
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
