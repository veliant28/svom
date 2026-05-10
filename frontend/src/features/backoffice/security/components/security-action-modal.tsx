"use client";

import { X } from "lucide-react";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import type { SecurityActor } from "@/features/backoffice/security/types/security.types";

export type SecurityActionKind = "whitelist" | "unwhitelist" | "extend" | "comment" | "falsePositive" | "reblock";

type Translator = (key: string, values?: Record<string, string | number>) => string;

export type SecurityActionTarget = {
  kind: SecurityActionKind;
  actor: SecurityActor;
} | null;

export function SecurityActionModal({
  target,
  t,
  isSubmitting,
  onClose,
  onConfirm,
}: {
  target: SecurityActionTarget;
  t: Translator;
  isSubmitting: boolean;
  onClose: () => void;
  onConfirm: (value: { reason: string; minutes: number }) => void;
}) {
  const [reason, setReason] = useState("");
  const [minutes, setMinutes] = useState(60);

  useEffect(() => {
    setReason("");
    setMinutes(60);
  }, [target?.kind, target?.actor.id]);

  if (!target || typeof document === "undefined") {
    return null;
  }

  const showMinutes = target.kind === "extend";
  const actionKey = target.kind;

  return createPortal(
    <div className="fixed inset-0 z-[1490] flex items-center justify-center bg-black/45 px-3" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-xl border shadow-2xl"
        style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b px-4 py-3" style={{ borderColor: "var(--border)" }}>
          <div className="min-w-0">
            <p className="font-semibold">{t(`modals.action.title.${actionKey}`)}</p>
            <p className="truncate text-xs" style={{ color: "var(--muted)" }}>
              {target.actor.source_identifier}
            </p>
          </div>
          <button type="button" className="rounded-md border p-2" style={{ borderColor: "var(--border)" }} aria-label={t("actions.close")} onClick={onClose}>
            <X className="size-4" />
          </button>
        </header>
        <div className="space-y-3 px-4 py-4">
          {showMinutes ? (
            <label className="grid gap-1 text-sm">
              <span className="font-medium">{t("modals.action.minutes")}</span>
              <input
                type="number"
                min={1}
                className="h-10 rounded-md border px-3"
                style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
                value={minutes}
                onChange={(event) => setMinutes(Math.max(1, Number(event.target.value) || 1))}
              />
            </label>
          ) : null}
          <label className="grid gap-1 text-sm">
            <span className="font-medium">{t(`modals.action.reason.${actionKey}`)}</span>
            <textarea
              className="min-h-24 rounded-md border px-3 py-2"
              style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>
        </div>
        <footer className="flex justify-end gap-2 border-t px-4 py-3" style={{ borderColor: "var(--border)" }}>
          <button type="button" className="rounded-md border px-3 py-2 text-sm" style={{ borderColor: "var(--border)" }} onClick={onClose}>
            {t("actions.cancel")}
          </button>
          <button
            type="button"
            className="rounded-md bg-slate-900 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
            disabled={isSubmitting || !reason.trim()}
            onClick={() => onConfirm({ reason, minutes })}
          >
            {t(`modals.action.confirm.${actionKey}`)}
          </button>
        </footer>
      </div>
    </div>,
    document.body,
  );
}
