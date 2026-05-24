"use client";

import { createElement, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { AlertTriangle, ArrowDown, CheckCircle2, CircleHelp, Clock3, LoaderCircle, MinusCircle, PackageCheck, Truck, XCircle } from "lucide-react";
import { useTranslations } from "next-intl";

import { normalizeStatusKey, normalizeStatusLabel } from "@/features/backoffice/lib/status";

export type StatusChipTone =
  | "success"
  | "warning"
  | "error"
  | "info"
  | "orange"
  | "gray"
  | "black"
  | "red"
  | "blue"
  | "violet"
  | "teal"
  | "brown";

export type StatusChipPalette = "default" | "countdown";

export const STATUS_CHIP_BASE_CLASS =
  "inline-flex w-fit items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-semibold";

const STATUS_CHIP_TONE_CLASSES: Record<StatusChipTone, string> = {
  success: "border-emerald-700/45 bg-emerald-700/16 text-emerald-900 dark:border-emerald-300/70 dark:bg-emerald-500/24 dark:text-emerald-50",
  warning: "border-amber-700/45 bg-amber-700/18 text-amber-900 dark:border-amber-300/70 dark:bg-amber-500/24 dark:text-amber-50",
  error: "border-red-700/45 bg-red-700/16 text-red-900 dark:border-red-300/70 dark:bg-red-500/24 dark:text-red-50",
  info: "border-slate-700/45 bg-slate-700/16 text-slate-900 dark:border-slate-300/70 dark:bg-slate-500/22 dark:text-slate-50",
  orange: "border-orange-700/45 bg-orange-700/16 text-orange-900 dark:border-orange-300/70 dark:bg-orange-500/24 dark:text-orange-50",
  gray: "border-zinc-700/45 bg-zinc-700/16 text-zinc-900 dark:border-zinc-300/70 dark:bg-zinc-500/22 dark:text-zinc-50",
  black: "border-neutral-900/70 bg-neutral-900/20 text-neutral-950 dark:border-neutral-100/70 dark:bg-neutral-100/12 dark:text-neutral-50",
  red: "border-red-700/45 bg-red-700/16 text-red-900 dark:border-red-300/70 dark:bg-red-500/24 dark:text-red-50",
  blue: "border-blue-700/45 bg-blue-700/16 text-blue-900 dark:border-blue-300/70 dark:bg-blue-500/24 dark:text-blue-50",
  violet: "border-violet-700/45 bg-violet-700/16 text-violet-900 dark:border-violet-300/70 dark:bg-violet-500/24 dark:text-violet-50",
  teal: "border-teal-700/45 bg-teal-700/16 text-teal-900 dark:border-teal-300/70 dark:bg-teal-500/24 dark:text-teal-50",
  brown: "border-amber-950/70 bg-amber-950/24 text-amber-950 dark:border-amber-300/65 dark:bg-amber-900/42 dark:text-amber-50",
};

const STATUS_CHIP_COUNTDOWN_CLASSES: Record<StatusChipTone, string> = {
  success: "border-blue-700/45 bg-blue-700/16 text-blue-900 dark:border-blue-300/70 dark:bg-blue-500/24 dark:text-blue-50",
  warning: STATUS_CHIP_TONE_CLASSES.warning,
  error: STATUS_CHIP_TONE_CLASSES.error,
  info: STATUS_CHIP_TONE_CLASSES.info,
  orange: STATUS_CHIP_TONE_CLASSES.orange,
  gray: STATUS_CHIP_TONE_CLASSES.gray,
  black: STATUS_CHIP_TONE_CLASSES.black,
  red: STATUS_CHIP_TONE_CLASSES.red,
  blue: STATUS_CHIP_TONE_CLASSES.blue,
  violet: STATUS_CHIP_TONE_CLASSES.violet,
  teal: STATUS_CHIP_TONE_CLASSES.teal,
  brown: STATUS_CHIP_TONE_CLASSES.brown,
};

function resolveToneClass(tone: StatusChipTone, palette: StatusChipPalette): string {
  if (palette === "countdown") {
    return STATUS_CHIP_COUNTDOWN_CLASSES[tone];
  }
  return STATUS_CHIP_TONE_CLASSES[tone];
}

const SUCCESS_STATUSES = new Set([
  "success",
  "processed",
  "enabled",
  "active",
  "ok",
  "matched",
  "connected",
  "ready_for_shipment",
  "shipped",
  "ready",
  "completed",
  "complete",
  "done",
  "downloaded",
  "imported",
  "auto_matched",
  "manually_matched",
  "auto_mapped",
  "manual_mapped",
]);

const ERROR_STATUSES = new Set([
  "failed",
  "error",
  "invalid",
  "expired",
  "canceled",
  "cancelled",
  "payment_failed",
  "supplier_unavailable",
  "unavailable",
  "disconnected",
]);

const WARNING_STATUSES = new Set([
  "partial",
  "attention",
  "warning",
  "manual_match_required",
  "confirmed",
  "partially_reserved",
  "awaiting_procurement",
  "customer_request",
  "supplier_shortage",
  "stock_shortage",
  "price_changed",
  "lead_time_too_long",
  "unmatched",
  "needs_review",
]);

const PROGRESS_STATUSES = new Set([
  "running",
  "in_progress",
  "processing",
  "generating",
  "placed",
]);

const QUEUED_STATUSES = new Set([
  "pending",
  "queued",
  "in_queue",
  "inqueue",
  "new",
  "draft",
  "blocked_by_cooldown",
]);

const NEUTRAL_STATUSES = new Set([
  "skipped",
  "disabled",
  "inactive",
  "unknown",
  "ignored",
  "operator_decision",
  "other",
]);

const ORDER_STATUS_META: Record<string, { tone: StatusChipTone; icon: LucideIcon }> = {
  new: { tone: "info", icon: Clock3 },
  processing: { tone: "blue", icon: LoaderCircle },
  ready_for_shipment: { tone: "orange", icon: PackageCheck },
  ready_to_ship: { tone: "orange", icon: PackageCheck },
  shipped: { tone: "brown", icon: Truck },
  completed: { tone: "success", icon: CheckCircle2 },
  cancelled: { tone: "error", icon: XCircle },
};

function resolveStatusTone(statusKey: string): StatusChipTone {
  if (ORDER_STATUS_META[statusKey]) {
    return ORDER_STATUS_META[statusKey].tone;
  }

  if (statusKey === "pending") {
    return "orange";
  }

  if (SUCCESS_STATUSES.has(statusKey)) {
    return "success";
  }

  if (ERROR_STATUSES.has(statusKey)) {
    return "error";
  }

  if (WARNING_STATUSES.has(statusKey)) {
    return "warning";
  }

  if (PROGRESS_STATUSES.has(statusKey)) {
    return "blue";
  }

  if (QUEUED_STATUSES.has(statusKey)) {
    return "info";
  }

  if (NEUTRAL_STATUSES.has(statusKey)) {
    return "gray";
  }

  return "gray";
}

function resolveStatusIcon(statusKey: string): LucideIcon {
  if (ORDER_STATUS_META[statusKey]) {
    return ORDER_STATUS_META[statusKey].icon;
  }

  if (statusKey === "downloaded") {
    return ArrowDown;
  }

  if (SUCCESS_STATUSES.has(statusKey)) {
    return CheckCircle2;
  }

  if (ERROR_STATUSES.has(statusKey)) {
    return XCircle;
  }

  if (WARNING_STATUSES.has(statusKey)) {
    return AlertTriangle;
  }

  if (PROGRESS_STATUSES.has(statusKey)) {
    return LoaderCircle;
  }

  if (QUEUED_STATUSES.has(statusKey)) {
    return Clock3;
  }

  if (NEUTRAL_STATUSES.has(statusKey)) {
    return MinusCircle;
  }

  return CircleHelp;
}

function renderStatusIconNode({
  statusKey,
  explicitIcon,
}: {
  statusKey: string;
  explicitIcon?: LucideIcon;
}): ReactNode {
  const className = "size-3.5 shrink-0";
  if (explicitIcon) {
    return createElement(explicitIcon, { className });
  }

  const Icon = resolveStatusIcon(statusKey);
  return createElement(Icon, { className });
}

function formatCountdown(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const remainder = safe % 60;

  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
  }

  return `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

export function StatusChip({
  status,
  countdownSeconds,
  tone,
  icon,
  palette = "default",
  className = "",
  children,
}: {
  status?: string;
  countdownSeconds?: number | null;
  tone?: StatusChipTone;
  icon?: LucideIcon;
  palette?: StatusChipPalette;
  className?: string;
  children?: ReactNode;
}) {
  const t = useTranslations("backoffice.common");
  const hasStatus = typeof status === "string" && status.trim().length > 0;
  const key = hasStatus ? normalizeStatusKey(status) : "unknown";
  const resolvedTone = tone ?? resolveStatusTone(key);
  const iconNode = hasStatus || icon
    ? renderStatusIconNode({ statusKey: key, explicitIcon: icon })
    : null;
  const hasCountdown =
    !children && hasStatus && key === "generating" && typeof countdownSeconds === "number" && Number.isFinite(countdownSeconds);
  const initialCountdown = hasCountdown ? Math.max(0, Math.floor(countdownSeconds)) : 0;
  const [secondsLeft, setSecondsLeft] = useState(initialCountdown);

  let label = t("statuses.unknown");
  if (hasStatus) {
    label = normalizeStatusLabel(status) || t("statuses.unknown");
    const translationKey = `statuses.${key}` as never;
    if (t.has(translationKey)) {
      label = t(translationKey);
    }
  }

  useEffect(() => {
    setSecondsLeft(initialCountdown);
  }, [initialCountdown]);

  useEffect(() => {
    if (!hasCountdown || secondsLeft <= 0) {
      return;
    }

    const timer = window.setInterval(() => {
      setSecondsLeft((prev) => Math.max(0, prev - 1));
    }, 1000);

    return () => window.clearInterval(timer);
  }, [hasCountdown, secondsLeft]);

  const content = useMemo(() => {
    if (children) {
      return children;
    }

    if (!hasCountdown) {
      return label;
    }

    return (
      <span className="inline-flex items-center gap-1.5">
        <span>{label}</span>
        <span className="tabular-nums">{formatCountdown(secondsLeft)}</span>
      </span>
    );
  }, [children, hasCountdown, label, secondsLeft]);

  return (
    <span className={`${STATUS_CHIP_BASE_CLASS} ${resolveToneClass(resolvedTone, palette)} ${className}`.trim()}>
      {iconNode}
      <span>{content}</span>
    </span>
  );
}
