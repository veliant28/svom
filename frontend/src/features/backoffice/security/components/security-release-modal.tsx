"use client";

import { X } from "lucide-react";
import { useState } from "react";
import { createPortal } from "react-dom";

import type { SecurityBlock } from "@/features/backoffice/security/types/security.types";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export function SecurityReleaseModal({
  block,
  t,
  isSubmitting,
  onClose,
  onConfirm,
}: {
  block: SecurityBlock | null;
  t: Translator;
  isSubmitting: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState("");
  if (!block || typeof document === "undefined") {
    return null;
  }

  return createPortal(
    <div className="fixed inset-0 z-[1500] flex items-center justify-center bg-black/45 px-3" onClick={onClose}>
      <div className="w-full max-w-lg rounded-xl border shadow-2xl" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }} onClick={(event) => event.stopPropagation()}>
        <header className="flex items-center justify-between border-b px-4 py-3" style={{ borderColor: "var(--border)" }}>
          <p className="font-semibold">{t("modals.release.title")}</p>
          <button type="button" className="rounded-md border p-2" style={{ borderColor: "var(--border)" }} aria-label={t("actions.close")} onClick={onClose}>
            <X className="size-4" />
          </button>
        </header>
        <div className="space-y-3 px-4 py-4">
          <div className="rounded-lg border p-3 text-sm" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}>
            <p className="font-semibold">{block.actor_source || block.value}</p>
            <p className="mt-1 text-xs" style={{ color: "var(--muted)" }}>{block.reason || t("block.noReason")}</p>
          </div>
          <label className="grid gap-1 text-sm">
            <span className="font-medium">{t("modals.release.reason")}</span>
            <textarea
              className="min-h-24 rounded-md border px-3 py-2"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>
        </div>
        <footer className="flex justify-end gap-2 border-t px-4 py-3" style={{ borderColor: "var(--border)" }}>
          <button type="button" className="rounded-md border px-3 py-2 text-sm" style={{ borderColor: "var(--border)" }} onClick={onClose}>{t("actions.cancel")}</button>
          <button
            type="button"
            className="rounded-md bg-red-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
            disabled={isSubmitting || !reason.trim()}
            onClick={() => onConfirm(reason)}
          >
            {t("actions.release")}
          </button>
        </footer>
      </div>
    </div>,
    document.body,
  );
}
