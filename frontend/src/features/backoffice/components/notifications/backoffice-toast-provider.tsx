"use client";

import type { LucideIcon } from "lucide-react";
import { AlertTriangle, CheckCircle2, CircleAlert, Info, X } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

export type BackofficeToastVariant = "success" | "error" | "warning" | "info";

type BackofficeToastInput = {
  message: string;
  variant?: BackofficeToastVariant;
  durationMs?: number;
};

type BackofficeToastRecord = {
  id: string;
  message: string;
  variant: BackofficeToastVariant;
  durationMs: number;
  closing: boolean;
};

type BackofficeToastContextValue = {
  show: (input: BackofficeToastInput) => string;
  success: (message: string, durationMs?: number) => string;
  error: (message: string, durationMs?: number) => string;
  warning: (message: string, durationMs?: number) => string;
  info: (message: string, durationMs?: number) => string;
  dismiss: (id: string) => void;
};

type ToastTimers = {
  autoHide?: ReturnType<typeof setTimeout>;
  remove?: ReturnType<typeof setTimeout>;
};

const DEFAULT_DURATIONS: Record<BackofficeToastVariant, number> = {
  success: 5_000,
  info: 5_000,
  warning: 5_000,
  error: 10_000,
};

type ToastPalette = {
  border: string;
  background: string;
  text: string;
  iconBg: string;
  iconColor: string;
};

const TOAST_COLORS: Record<BackofficeToastVariant, ToastPalette> = {
  success: {
    border: "#22c55e",
    background: "linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%)",
    text: "#14532d",
    iconBg: "#86efac",
    iconColor: "#166534",
  },
  error: {
    border: "#fb7185",
    background: "linear-gradient(135deg, #ffe4e6 0%, #fecdd3 100%)",
    text: "#881337",
    iconBg: "#fda4af",
    iconColor: "#be123c",
  },
  warning: {
    border: "#fb923c",
    background: "linear-gradient(135deg, #ffedd5 0%, #fed7aa 100%)",
    text: "#8a430b",
    iconBg: "#fdba74",
    iconColor: "#c2410c",
  },
  info: {
    border: "#3b82f6",
    background: "linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%)",
    text: "#1e3a8a",
    iconBg: "#93c5fd",
    iconColor: "#1d4ed8",
  },
};

const TOAST_ICONS: Record<BackofficeToastVariant, LucideIcon> = {
  success: CheckCircle2,
  error: CircleAlert,
  warning: AlertTriangle,
  info: Info,
};

const BackofficeToastContext = createContext<BackofficeToastContextValue | null>(null);

function resolveDuration(variant: BackofficeToastVariant, durationMs?: number) {
  return durationMs && durationMs > 0 ? durationMs : DEFAULT_DURATIONS[variant];
}

export function BackofficeToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<BackofficeToastRecord[]>([]);
  const counterRef = useRef(0);
  const timersRef = useRef<Map<string, ToastTimers>>(new Map());
  const dedupeRef = useRef<Map<string, number>>(new Map());

  const clearToastTimers = useCallback((id: string) => {
    const timers = timersRef.current.get(id);
    if (!timers) {
      return;
    }
    if (timers.autoHide) {
      clearTimeout(timers.autoHide);
    }
    if (timers.remove) {
      clearTimeout(timers.remove);
    }
    timersRef.current.delete(id);
  }, []);

  const removeToast = useCallback(
    (id: string) => {
      clearToastTimers(id);
      setToasts((current) => current.filter((toast) => toast.id !== id));
    },
    [clearToastTimers],
  );

  const dismiss = useCallback(
    (id: string) => {
      setToasts((current) =>
        current.map((toast) => (toast.id === id && !toast.closing ? { ...toast, closing: true } : toast)),
      );

      const existingTimers = timersRef.current.get(id) ?? {};
      if (existingTimers.autoHide) {
        clearTimeout(existingTimers.autoHide);
        existingTimers.autoHide = undefined;
      }
      if (existingTimers.remove) {
        clearTimeout(existingTimers.remove);
      }
      existingTimers.remove = setTimeout(() => {
        removeToast(id);
      }, 220);
      timersRef.current.set(id, existingTimers);
    },
    [removeToast],
  );

  const show = useCallback(
    ({ message, variant = "info", durationMs }: BackofficeToastInput) => {
      const normalizedMessage = message.trim();
      if (!normalizedMessage) {
        return "";
      }

      const dedupeKey = `${variant}:${normalizedMessage}`;
      const now = Date.now();
      const lastShownAt = dedupeRef.current.get(dedupeKey);
      if (lastShownAt && now - lastShownAt < 1_000) {
        return "";
      }
      dedupeRef.current.set(dedupeKey, now);

      const id = `bo-toast-${now}-${counterRef.current}`;
      counterRef.current += 1;

      const toast: BackofficeToastRecord = {
        id,
        message: normalizedMessage,
        variant,
        durationMs: resolveDuration(variant, durationMs),
        closing: false,
      };
      setToasts((current) => [...current, toast]);

      const existingTimers = timersRef.current.get(id) ?? {};
      existingTimers.autoHide = setTimeout(() => {
        dismiss(id);
      }, toast.durationMs);
      timersRef.current.set(id, existingTimers);

      return id;
    },
    [dismiss],
  );

  useEffect(() => {
    const timers = timersRef.current;
    return () => {
      timers.forEach((entry) => {
        if (entry.autoHide) {
          clearTimeout(entry.autoHide);
        }
        if (entry.remove) {
          clearTimeout(entry.remove);
        }
      });
      timers.clear();
    };
  }, []);

  const value = useMemo<BackofficeToastContextValue>(
    () => ({
      show,
      success: (message, durationMs) => show({ message, variant: "success", durationMs }),
      error: (message, durationMs) => show({ message, variant: "error", durationMs }),
      warning: (message, durationMs) => show({ message, variant: "warning", durationMs }),
      info: (message, durationMs) => show({ message, variant: "info", durationMs }),
      dismiss,
    }),
    [dismiss, show],
  );

  return (
    <BackofficeToastContext.Provider value={value}>
      {children}

      <div
        aria-live="polite"
        aria-relevant="additions removals"
        className="pointer-events-none fixed bottom-4 right-4 z-[80] flex w-[min(92vw,24rem)] flex-col gap-2"
      >
        {toasts.map((toast) => {
          const palette = TOAST_COLORS[toast.variant];
          const Icon = TOAST_ICONS[toast.variant];
          return (
            <div
              key={toast.id}
              role={toast.variant === "error" ? "alert" : "status"}
              className="pointer-events-auto rounded-xl border p-3 shadow-lg transition-all duration-200"
              style={{
                borderColor: palette.border,
                background: palette.background,
                color: palette.text,
                opacity: toast.closing ? 0 : 1,
                transform: toast.closing ? "translateY(8px) scale(0.98)" : "translateY(0) scale(1)",
              }}
            >
              <div className="flex items-center gap-2.5">
                <span
                  className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md"
                  style={{ backgroundColor: palette.iconBg, color: palette.iconColor }}
                >
                  <Icon size={18} />
                </span>
                <p className="flex-1 text-sm leading-snug">{toast.message}</p>
                <button
                  type="button"
                  className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md border"
                  style={{ borderColor: palette.border, color: palette.text }}
                  aria-label="Dismiss notification"
                  onClick={() => dismiss(toast.id)}
                >
                  <X size={14} />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </BackofficeToastContext.Provider>
  );
}

export function useBackofficeToast() {
  const context = useContext(BackofficeToastContext);
  if (!context) {
    throw new Error("useBackofficeToast must be used within BackofficeToastProvider.");
  }
  return context;
}
