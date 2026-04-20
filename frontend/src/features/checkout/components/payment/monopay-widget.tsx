"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Script from "next/script";

import { MONOBANK_OFFICIAL_WIDGETS_ENABLED } from "@/features/checkout/lib/monobank-widget-flags";
import type { MonobankWidgetInit } from "@/features/checkout/types/payment";
import { useTheme } from "@/shared/components/theme/theme-provider";

type MonoPayInitResult = {
  button?: HTMLElement;
};

declare global {
  interface Window {
    MonoPay?: {
      init: (config: {
        keyId: string;
        signature: string;
        requestId: string;
        payloadBase64: string;
        ui?: {
          buttonType?: "pay";
          theme?: "dark" | "light";
          corners?: "rounded" | "square";
        };
        callbacks?: {
          onSuccess?: (payload: unknown) => void;
          onError?: (error: unknown) => void;
        };
      }) => MonoPayInitResult;
    };
  }
}

export function MonoPayWidget({
  widget,
  pageUrl,
  t,
}: {
  widget: MonobankWidgetInit | null;
  pageUrl: string;
  t: (key: string) => string;
}) {
  const { theme } = useTheme();
  const [scriptLoaded, setScriptLoaded] = useState(false);
  const [widgetFailed, setWidgetFailed] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const canInitWidget = useMemo(() => Boolean(scriptLoaded && widget), [scriptLoaded, widget]);

  useEffect(() => {
    if (!MONOBANK_OFFICIAL_WIDGETS_ENABLED) {
      setWidgetFailed(true);
      return;
    }

    const widgetPayload = widget;
    if (!canInitWidget || !widgetPayload || !containerRef.current || !window.MonoPay) {
      return;
    }

    containerRef.current.innerHTML = "";

    try {
      const result = window.MonoPay.init({
        keyId: widgetPayload.key_id,
        signature: widgetPayload.signature,
        requestId: widgetPayload.request_id,
        payloadBase64: widgetPayload.payload_base64,
        ui: {
          buttonType: "pay",
          theme: theme === "dark" ? "light" : "dark",
          corners: "rounded",
        },
      });

      if (!result?.button) {
        setWidgetFailed(true);
        return;
      }

      containerRef.current.appendChild(result.button);
      setWidgetFailed(false);
    } catch {
      setWidgetFailed(true);
    }
  }, [canInitWidget, theme, widget]);

  return (
    <div className="grid gap-3">
      {MONOBANK_OFFICIAL_WIDGETS_ENABLED ? (
        <Script
          src="https://pay.monobank.ua/mono-pay-button/v1/mono-pay-button.js"
          strategy="afterInteractive"
          onLoad={() => {
            setScriptLoaded(true);
          }}
          onError={() => {
            setWidgetFailed(true);
          }}
        />
      ) : null}

      <div className="rounded-xl border p-4" style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
        <p className="text-sm font-semibold">{t("payment.payWithMonobank")}</p>
        {!scriptLoaded ? <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>{t("payment.widgetLoading")}</p> : null}
        <div ref={containerRef} className="mt-3 min-h-11" />

        {widgetFailed ? <p className="text-xs" style={{ color: "var(--danger, #b42318)" }}>{t("payment.widgetFailedFallback")}</p> : null}

        {pageUrl ? (
          <a
            href={pageUrl}
            target="_blank"
            rel="noreferrer"
            className="mt-3 inline-flex rounded-md border px-3 py-2 text-xs font-semibold"
            style={{ borderColor: "var(--border)", backgroundColor: "var(--surface-2)" }}
          >
            {t("payment.openMonobankPage")}
          </a>
        ) : null}
      </div>
    </div>
  );
}
