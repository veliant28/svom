"use client";

import { useEffect, useMemo, useState } from "react";
import type { LucideIcon } from "lucide-react";
import { AlertTriangle, ArrowDown, CheckCircle2, CircleHelp, Clock3, LoaderCircle, MinusCircle, PackageCheck, Truck, XCircle } from "lucide-react";
import { useTranslations } from "next-intl";

import { normalizeStatusKey, normalizeStatusLabel } from "@/features/backoffice/lib/status";

import { BackofficeStatusChip, type BackofficeStatusChipTone } from "./backoffice-status-chip";

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

const ORDER_STATUS_META: Record<string, { tone: BackofficeStatusChipTone; icon: LucideIcon }> = {
  new: { tone: "info", icon: Clock3 },
  processing: { tone: "blue", icon: LoaderCircle },
  ready_for_shipment: { tone: "orange", icon: PackageCheck },
  ready_to_ship: { tone: "orange", icon: PackageCheck },
  shipped: { tone: "brown", icon: Truck },
  completed: { tone: "success", icon: CheckCircle2 },
  cancelled: { tone: "error", icon: XCircle },
};

function resolveStatusTone(statusKey: string): BackofficeStatusChipTone {
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
}: {
  status: string;
  countdownSeconds?: number | null;
}) {
  const t = useTranslations("backoffice.common");
  const key = normalizeStatusKey(status);
  const tone = resolveStatusTone(key);
  const icon = resolveStatusIcon(key);
  const hasCountdown = key === "generating" && typeof countdownSeconds === "number" && Number.isFinite(countdownSeconds);
  const initialCountdown = hasCountdown ? Math.max(0, Math.floor(countdownSeconds)) : 0;
  const [secondsLeft, setSecondsLeft] = useState(initialCountdown);

  let label = normalizeStatusLabel(status) || t("statuses.unknown");
  try {
    label = t(`statuses.${key}`);
  } catch {
    // Keep fallback label when translation key is missing.
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
    if (!hasCountdown) {
      return label;
    }

    return (
      <span className="inline-flex items-center gap-1.5">
        <span>{label}</span>
        <span className="tabular-nums">{formatCountdown(secondsLeft)}</span>
      </span>
    );
  }, [hasCountdown, label, secondsLeft]);

  return (
    <BackofficeStatusChip tone={tone} icon={icon}>
      {content}
    </BackofficeStatusChip>
  );
}
