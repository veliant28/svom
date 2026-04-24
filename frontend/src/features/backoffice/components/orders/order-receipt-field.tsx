"use client";

import { AlertCircle, ExternalLink, LoaderCircle, RefreshCw, Receipt } from "lucide-react";

import type { BackofficeOrderReceiptSummary } from "@/features/backoffice/types/vchasno-kasa.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

function resolveStatusLabel(receipt: BackofficeOrderReceiptSummary, t: Translator): string {
  const statusKey = (receipt.status_key || "").trim() || "pending";
  const key = `orders.receipt.status.${statusKey}`;
  const translated = t(key);
  return translated === key ? (receipt.status_label || t("orders.receipt.status.pending")) : translated;
}

export function OrderReceiptField({
  receipt,
  isLoading,
  onIssue,
  onSync,
  onOpen,
  t,
}: {
  receipt: BackofficeOrderReceiptSummary | null | undefined;
  isLoading: "issue" | "sync" | "open" | null;
  onIssue: () => void;
  onSync: () => void;
  onOpen: () => void;
  t: Translator;
}) {
  const statusLabel = receipt ? resolveStatusLabel(receipt, t) : t("orders.receipt.status.notCreated");

  return (
    <div className="rounded-md border px-3 py-2" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
      <p className="text-[11px]" style={{ color: "var(--muted)" }}>{t("orders.receipt.label")}</p>
      <div className="mt-1 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-medium text-[var(--text)]">{statusLabel}</p>
          {receipt?.check_fn ? (
            <p className="mt-0.5 font-mono text-xs" style={{ color: "var(--muted)" }}>{receipt.check_fn}</p>
          ) : null}
          {receipt?.error_message ? (
            <p className="mt-1 flex items-start gap-1 text-[11px]" style={{ color: "#b91c1c" }}>
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span className="line-clamp-2">{receipt.error_message}</span>
            </p>
          ) : null}
        </div>

        <div className="flex shrink-0 items-center gap-1">
          {receipt?.can_issue ? (
            <button
              type="button"
              className="inline-flex h-8 items-center gap-1 rounded-md border px-2 text-xs font-semibold disabled:opacity-60"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              onClick={onIssue}
              disabled={Boolean(isLoading)}
            >
              {isLoading === "issue" ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <Receipt className="h-3.5 w-3.5" />}
              {t("orders.receipt.actions.issue")}
            </button>
          ) : null}
          {receipt?.can_sync ? (
            <button
              type="button"
              className="inline-flex h-8 items-center gap-1 rounded-md border px-2 text-xs font-semibold disabled:opacity-60"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              onClick={onSync}
              disabled={Boolean(isLoading)}
            >
              {isLoading === "sync" ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
              {t("orders.receipt.actions.sync")}
            </button>
          ) : null}
          {receipt?.can_open ? (
            <button
              type="button"
              className="inline-flex h-8 items-center gap-1 rounded-md border px-2 text-xs font-semibold disabled:opacity-60"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              onClick={onOpen}
              disabled={Boolean(isLoading)}
            >
              {isLoading === "open" ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <ExternalLink className="h-3.5 w-3.5" />}
              {t("orders.receipt.actions.open")}
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
